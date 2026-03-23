import asyncio
import base64
import json
import time
import uuid
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache

from crop_predication_chatbot.jwt_utils import JwtError, JwtExpiredError, decode_jwt
from crop_predication_chatbot.security import websocket_logger
from home.models import userProfile

from .conversation_ai_service import ConversationAIService
from .speech_recognition_service import SpeechRecognitionService


class RealtimeAudioGateway:
    def __init__(self) -> None:
        self.asr_service = SpeechRecognitionService()
        self.conversation_service = ConversationAIService()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'websocket':
            raise RuntimeError('RealtimeAudioGateway only supports websocket scopes.')

        query = parse_qs(scope.get('query_string', b'').decode('utf-8'))
        session_id = (query.get('session_id') or [''])[0]
        token = (query.get('token') or [''])[0]
        client_ip = self._get_client_ip(scope)

        if not self._allow_connection(client_ip):
            websocket_logger.warning('Websocket rate limit exceeded ip=%s path=%s', client_ip, scope.get('path'))
            await send({'type': 'websocket.close', 'code': 4429})
            return

        if not session_id or not token:
            websocket_logger.warning('Unauthorized websocket connection missing token/session ip=%s', client_ip)
            await send({'type': 'websocket.close', 'code': 4400})
            return

        try:
            uuid.UUID(session_id)
        except ValueError:
            websocket_logger.warning('Unauthorized websocket connection invalid session ip=%s', client_ip)
            await send({'type': 'websocket.close', 'code': 4400})
            return

        try:
            claims = decode_jwt(token)
        except JwtExpiredError:
            websocket_logger.warning('Expired websocket token rejected ip=%s', client_ip)
            await send({'type': 'websocket.close', 'code': 4401})
            return
        except JwtError:
            websocket_logger.warning('Invalid websocket token rejected ip=%s', client_ip)
            await send({'type': 'websocket.close', 'code': 4403})
            return

        if claims.get('role') != 'user':
            websocket_logger.warning('Non-user websocket token rejected role=%s ip=%s', claims.get('role'), client_ip)
            await send({'type': 'websocket.close', 'code': 4403})
            return

        user = await sync_to_async(userProfile.objects.filter(email__iexact=claims.get('email', '')).first)()
        if not user or user.status.lower() != 'activated':
            websocket_logger.warning('Unauthorized websocket user rejected email=%s ip=%s', claims.get('email'), client_ip)
            await send({'type': 'websocket.close', 'code': 4403})
            return

        conversation_session = await sync_to_async(self.conversation_service.get_or_create_session)(session_id, user)
        audio_buffer = bytearray()

        await send({'type': 'websocket.accept'})
        await self._send_json(send, {
            'type': 'session.ready',
            'session_id': session_id,
            'message': 'Realtime gateway connected.',
            'providers': {
                'asr_configured': self.asr_service.is_configured(),
                'tts_configured': self.conversation_service.tts_service.is_configured(),
                'ai_configured': self.conversation_service.is_configured(),
            },
        })

        while True:
            event = await receive()
            if event['type'] == 'websocket.disconnect':
                break

            if event['type'] != 'websocket.receive':
                continue

            if event.get('text'):
                payload = json.loads(event['text'])
                message_type = payload.get('type')

                if message_type == 'ping':
                    await self._send_json(send, {'type': 'pong'})
                elif message_type == 'audio_chunk':
                    chunk = payload.get('audio')
                    if chunk:
                        audio_buffer.extend(base64.b64decode(chunk))
                        await self._send_json(send, {'type': 'audio.buffered', 'size': len(audio_buffer)})
                elif message_type == 'commit_audio':
                    await self._handle_audio_commit(send, conversation_session, bytes(audio_buffer))
                    audio_buffer.clear()
                elif message_type == 'user_text':
                    await self._handle_user_text(send, conversation_session, payload.get('text', ''))
                elif message_type == 'reset_audio':
                    audio_buffer.clear()
                    await self._send_json(send, {'type': 'audio.reset'})
            elif event.get('bytes'):
                audio_buffer.extend(event['bytes'])

    def _allow_connection(self, client_ip: str) -> bool:
        window = int(time.time() // settings.RATE_LIMIT_WINDOW_SECONDS)
        cache_key = f'ws-conn:{client_ip}:{window}'
        try:
            count = cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, timeout=settings.RATE_LIMIT_WINDOW_SECONDS)
            count = 1
        return count <= settings.WEBSOCKET_CONNECT_RATE_LIMIT

    def _get_client_ip(self, scope) -> str:
        client = scope.get('client')
        if client and client[0]:
            return client[0]
        return 'unknown'

    async def _handle_audio_commit(self, send, conversation_session, audio_bytes: bytes):
        await self._send_json(send, {'type': 'assistant.status', 'status': 'transcribing'})
        asr_result = await asyncio.to_thread(self.asr_service.transcribe_audio, audio_bytes, 'te-IN')

        if asr_result.confidence < self.asr_service.confidence_threshold or not asr_result.transcript:
            turn = await sync_to_async(self.conversation_service.build_low_confidence_reply)(
                conversation_session,
                'Low-confidence ASR fallback triggered.',
                asr_result.confidence,
                {'asr_provider': asr_result.provider, 'asr_raw': asr_result.raw},
            )
            await self._send_turn(send, turn)
            return

        await self._handle_processed_text(
            send,
            conversation_session,
            transcript=asr_result.transcript,
            source='voice',
            asr_confidence=asr_result.confidence,
            model_metadata={'asr_provider': asr_result.provider, 'asr_raw': asr_result.raw},
        )

    async def _handle_user_text(self, send, conversation_session, text: str):
        await self._handle_processed_text(
            send,
            conversation_session,
            transcript=text,
            source='text',
            asr_confidence=None,
            model_metadata={'input_mode': 'typed_fallback'},
        )

    async def _handle_processed_text(
        self,
        send,
        conversation_session,
        transcript: str,
        source: str,
        asr_confidence,
        model_metadata,
    ):
        await self._send_json(send, {'type': 'assistant.status', 'status': 'thinking'})
        turn = await sync_to_async(self.conversation_service.process_user_text)(
            conversation_session,
            transcript,
            source=source,
            language='te-IN',
            asr_confidence=asr_confidence,
            model_metadata=model_metadata,
        )
        await self._send_turn(send, turn)

    async def _send_turn(self, send, turn):
        await self._send_json(send, {
            'type': 'assistant.turn',
            'transcript': turn.transcript,
            'normalized_text': turn.normalized_text,
            'intent': turn.intent,
            'parameters': turn.parameters,
            'missing_parameters': turn.missing_parameters,
            'prediction': turn.prediction,
            'class_probabilities': turn.class_probabilities,
            'assistant_text': turn.assistant_text,
            'audio_base64': turn.audio_base64,
            'audio_url': turn.audio_url,
            'asr_confidence': turn.asr_confidence,
            'low_confidence': turn.low_confidence,
            'fallback_to_text': turn.fallback_to_text,
            'model_metadata': turn.model_metadata,
        })

    async def _send_json(self, send, payload):
        await send({
            'type': 'websocket.send',
            'text': json.dumps(payload),
        })


application = RealtimeAudioGateway()
