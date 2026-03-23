import base64
import io
import json
import logging
import os
import wave
from dataclasses import dataclass, field
from typing import Any, Dict

import requests

try:
    from vosk import KaldiRecognizer, Model, SetLogLevel
except ImportError:  # pragma: no cover
    KaldiRecognizer = None
    Model = None
    SetLogLevel = None

asr_logger = logging.getLogger('api_security')


@dataclass
class ASRResult:
    transcript: str = ''
    confidence: float = 0.0
    language: str = 'te-IN'
    provider: str = 'fallback'
    raw: Dict[str, Any] = field(default_factory=dict)


class SpeechRecognitionService:
    _vosk_model_cache: dict[str, Any] = {}

    def __init__(self) -> None:
        self.endpoint = os.getenv('NVIDIA_PARAKEET_ASR_URL', '').strip()
        self.api_key = (
            os.getenv('NVIDIA_PARAKEET_API_KEY', '').strip()
            or os.getenv('NVIDIA_API_KEY', '').strip()
        )
        self.function_id = os.getenv('NVIDIA_PARAKEET_FUNCTION_ID', '').strip()
        self.confidence_threshold = float(os.getenv('VOICE_ASR_CONFIDENCE_THRESHOLD', '0.55'))

        self.vosk_model_path = os.getenv('VOSK_MODEL_PATH', '').strip()
        self.vosk_sample_rate = int(os.getenv('VOSK_SAMPLE_RATE', '16000'))

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: str = 'te-IN',
        mime_type: str = 'audio/wav',
        filename: str = 'voice.wav',
    ) -> ASRResult:
        if self.is_vosk_configured():
            result = self._transcribe_with_vosk(audio_bytes, language, mime_type=mime_type, filename=filename)
            if result.transcript:
                return result
            asr_logger.warning('ASR provider=vosk falling_back_to_nvidia raw=%s', result.raw)

        if self.endpoint:
            return self._transcribe_with_nvidia(audio_bytes, language, mime_type=mime_type, filename=filename)

        if self.api_key and self.function_id:
            return self._transcribe_with_nvcf(audio_bytes, language, mime_type=mime_type, filename=filename)

        asr_logger.warning(
            'ASR provider=fallback reason=missing_configuration language=%s endpoint=%s function_id=%s vosk=%s',
            language,
            bool(self.endpoint),
            bool(self.function_id),
            self.is_vosk_configured(),
        )
        return ASRResult(
            transcript='',
            confidence=0.0,
            language=language,
            provider='fallback',
            raw={'reason': 'Set VOSK_MODEL_PATH or NVIDIA ASR configuration.'},
        )

    def is_configured(self) -> bool:
        return self.is_vosk_configured() or bool(self.endpoint or (self.api_key and self.function_id))

    def is_vosk_configured(self) -> bool:
        return bool(Model is not None and self.vosk_model_path and os.path.exists(self.vosk_model_path))

    def _transcribe_with_vosk(self, audio_bytes: bytes, language: str, *, mime_type: str, filename: str) -> ASRResult:
        if Model is None or KaldiRecognizer is None:
            return ASRResult(
                transcript='',
                confidence=0.0,
                language=language,
                provider='fallback',
                raw={'reason': 'vosk is not installed.'},
            )

        if SetLogLevel is not None:
            SetLogLevel(-1)

        try:
            pcm_bytes, sample_rate = self._extract_wav_pcm(audio_bytes)
        except ValueError as exc:
            asr_logger.warning('ASR provider=vosk invalid_audio error=%s mime_type=%s filename=%s', exc, mime_type, filename)
            return ASRResult(
                transcript='',
                confidence=0.0,
                language=language,
                provider='fallback',
                raw={'reason': str(exc), 'mime_type': mime_type, 'filename': filename},
            )

        try:
            model = self._get_vosk_model()
            recognizer = KaldiRecognizer(model, sample_rate)
            recognizer.SetWords(True)
            chunk_size = 4000
            for index in range(0, len(pcm_bytes), chunk_size):
                recognizer.AcceptWaveform(pcm_bytes[index:index + chunk_size])
            final_result = json.loads(recognizer.FinalResult() or '{}')
        except Exception as exc:  # pragma: no cover
            asr_logger.warning('ASR provider=vosk request_failed error=%s', exc)
            return ASRResult(
                transcript='',
                confidence=0.0,
                language=language,
                provider='fallback',
                raw={'reason': str(exc)},
            )

        transcript = str(final_result.get('text', '') or '').strip()
        confidence = self._average_confidence(final_result.get('result', []))
        asr_logger.info(
            'ASR provider=vosk normalized transcript_present=%s confidence=%s sample_rate=%s',
            bool(transcript),
            confidence,
            sample_rate,
        )
        return ASRResult(
            transcript=transcript,
            confidence=confidence,
            language=language,
            provider='vosk',
            raw=final_result,
        )

    def _get_vosk_model(self):
        cache_key = self.vosk_model_path
        model = self._vosk_model_cache.get(cache_key)
        if model is None:
            model = Model(self.vosk_model_path)
            self._vosk_model_cache[cache_key] = model
        return model

    def _extract_wav_pcm(self, audio_bytes: bytes) -> tuple[bytes, int]:
        with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
            sample_width = wav_file.getsampwidth()
            channels = wav_file.getnchannels()
            sample_rate = wav_file.getframerate()
            frames = wav_file.readframes(wav_file.getnframes())

        if sample_width != 2:
            raise ValueError(f'Vosk expects 16-bit PCM WAV audio, received sample width {sample_width}.')

        if channels == 2:
            frames = self._stereo_to_mono(frames)
        elif channels != 1:
            raise ValueError(f'Unsupported channel count for Vosk: {channels}.')

        return frames, sample_rate

    def _stereo_to_mono(self, frames: bytes) -> bytes:
        mono = bytearray()
        for index in range(0, len(frames), 4):
            left = int.from_bytes(frames[index:index + 2], byteorder='little', signed=True)
            right = int.from_bytes(frames[index + 2:index + 4], byteorder='little', signed=True)
            mixed = int((left + right) / 2)
            mono.extend(int(mixed).to_bytes(2, byteorder='little', signed=True))
        return bytes(mono)

    def _average_confidence(self, words: Any) -> float:
        if not isinstance(words, list) or not words:
            return 0.0
        confidences = []
        for item in words:
            if isinstance(item, dict):
                try:
                    confidences.append(float(item.get('conf', 0.0) or 0.0))
                except (TypeError, ValueError):
                    continue
        if not confidences:
            return 0.0
        return sum(confidences) / len(confidences)

    def _transcribe_with_nvidia(self, audio_bytes: bytes, language: str, *, mime_type: str, filename: str) -> ASRResult:
        audio_format = self._guess_audio_format(mime_type, filename)
        payload = {
            'audio_base64': base64.b64encode(audio_bytes).decode('utf-8'),
            'language_code': language,
            'format': audio_format,
            'mime_type': mime_type,
            'filename': filename,
            'model': 'parakeet-multilingual',
        }
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        try:
            response = requests.post(self.endpoint, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            self._log_provider_response('nvidia_parakeet', data)
        except requests.HTTPError as exc:
            self._log_http_error('nvidia_parakeet', exc.response)
            return ASRResult(
                transcript='',
                confidence=0.0,
                language=language,
                provider='fallback',
                raw={'reason': str(exc), 'status_code': getattr(exc.response, 'status_code', None)},
            )
        except requests.RequestException as exc:
            asr_logger.warning('ASR provider=nvidia_parakeet request_failed error=%s', exc)
            return ASRResult(
                transcript='',
                confidence=0.0,
                language=language,
                provider='fallback',
                raw={'reason': str(exc)},
            )
        except ValueError as exc:
            asr_logger.warning('ASR provider=nvidia_parakeet invalid_json error=%s', exc)
            return ASRResult(
                transcript='',
                confidence=0.0,
                language=language,
                provider='fallback',
                raw={'reason': f'Invalid JSON response: {exc}'},
            )

        transcript, confidence, detected_language = self._normalize_asr_payload(data, language)
        asr_logger.info(
            'ASR provider=nvidia_parakeet normalized transcript_present=%s confidence=%s language=%s',
            bool(transcript),
            confidence,
            detected_language,
        )
        return ASRResult(
            transcript=transcript,
            confidence=confidence,
            language=detected_language,
            provider='nvidia_parakeet',
            raw=data,
        )

    def _transcribe_with_nvcf(self, audio_bytes: bytes, language: str, *, mime_type: str, filename: str) -> ASRResult:
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        encoded_audio = base64.b64encode(audio_bytes).decode('utf-8')
        audio_format = self._guess_audio_format(mime_type, filename)

        payload_variants = [
            {'requestBody': {'audio_base64': encoded_audio, 'language_code': language, 'format': audio_format, 'mime_type': mime_type, 'filename': filename}},
            {'requestBody': {'audio': encoded_audio, 'language': language, 'audio_format': audio_format, 'mime_type': mime_type, 'filename': filename}},
            {'requestBody': {'input': {'audio_base64': encoded_audio, 'language_code': language, 'format': audio_format, 'mime_type': mime_type, 'filename': filename}}},
            {'requestBody': {'content': encoded_audio, 'content_type': mime_type, 'language_code': language, 'format': audio_format, 'filename': filename}},
            {'requestBody': {'audio_bytes': encoded_audio, 'content_type': mime_type, 'language_code': language, 'format': audio_format, 'filename': filename}},
            {'requestBody': {'audio_data': encoded_audio, 'mime_type': mime_type, 'language_code': language, 'format': audio_format, 'filename': filename}},
            {'requestBody': {'input': {'audio': encoded_audio, 'language': language, 'audio_format': audio_format, 'mime_type': mime_type, 'filename': filename}}},
            {'requestBody': {'data': {'audio_base64': encoded_audio, 'language_code': language, 'format': audio_format, 'mime_type': mime_type, 'filename': filename}}},
            {'requestBody': {'audio_base64': encoded_audio, 'language_code': language, 'format': audio_format, 'mime_type': mime_type, 'filename': filename, 'task': 'transcribe', 'model': 'parakeet-multilingual'}},
            {'requestBody': {'input': {'audio_base64': encoded_audio, 'language_code': language, 'format': audio_format, 'mime_type': mime_type, 'filename': filename}, 'task': 'transcribe', 'model': 'parakeet-multilingual'}},
            {'requestBody': {'audio': {'content': encoded_audio, 'mime_type': mime_type, 'filename': filename, 'format': audio_format}, 'language_code': language}},
            {'requestBody': {'input_audio': {'audio_base64': encoded_audio, 'mime_type': mime_type, 'filename': filename, 'format': audio_format}, 'language_code': language}},
        ]

        last_error: Dict[str, Any] | None = None
        for index, payload in enumerate(payload_variants, start=1):
            try:
                response = requests.post(
                    f'https://api.nvcf.nvidia.com/v2/nvcf/exec/functions/{self.function_id}',
                    json=payload,
                    headers=headers,
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json() if response.content else {}
                self._log_provider_response(f'nvidia_nvcf_parakeet_variant_{index}', data)
                transcript, confidence, detected_language = self._normalize_asr_payload(data, language)
                asr_logger.info(
                    'ASR provider=nvidia_nvcf_parakeet normalized variant=%s transcript_present=%s confidence=%s language=%s',
                    index,
                    bool(transcript),
                    confidence,
                    detected_language,
                )
                return ASRResult(
                    transcript=transcript,
                    confidence=confidence,
                    language=detected_language,
                    provider='nvidia_nvcf_parakeet',
                    raw=data,
                )
            except requests.HTTPError as exc:
                response = exc.response
                self._log_http_error(f'nvidia_nvcf_parakeet_variant_{index}', response)
                last_error = {
                    'reason': str(exc),
                    'status_code': getattr(response, 'status_code', None),
                    'body': self._safe_response_text(response),
                    'variant': index,
                }
                status_code = getattr(response, 'status_code', None)
                if status_code in {401, 403, 404, 405, 429}:
                    break
            except requests.RequestException as exc:
                asr_logger.warning('ASR provider=nvidia_nvcf_parakeet request_failed variant=%s error=%s', index, exc)
                last_error = {'reason': str(exc), 'variant': index}
                break
            except ValueError as exc:
                asr_logger.warning('ASR provider=nvidia_nvcf_parakeet invalid_json variant=%s error=%s', index, exc)
                last_error = {'reason': f'Invalid JSON response: {exc}', 'variant': index}
                break

        return ASRResult(
            transcript='',
            confidence=0.0,
            language=language,
            provider='fallback',
            raw=last_error or {'reason': 'Unknown ASR failure.'},
        )

    def _guess_audio_format(self, mime_type: str, filename: str) -> str:
        candidate = (mime_type or '').lower()
        filename = (filename or '').lower()
        if 'ogg' in candidate or filename.endswith('.ogg'):
            return 'ogg-opus'
        if 'mp4' in candidate or filename.endswith('.mp4') or filename.endswith('.m4a'):
            return 'mp4'
        if 'wav' in candidate or filename.endswith('.wav'):
            return 'wav'
        return 'webm-opus'

    def _normalize_asr_payload(self, data: Dict[str, Any], default_language: str) -> tuple[str, float, str]:
        transcript = self._extract_first_string(
            data,
            (
                ('transcript',),
                ('text',),
                ('result', 'transcript'),
                ('result', 'text'),
                ('output', 'transcript'),
                ('output', 'text'),
                ('data', 'transcript'),
                ('data', 'text'),
                ('predictions', 0, 'transcript'),
                ('predictions', 0, 'text'),
                ('choices', 0, 'message', 'content'),
            ),
        )
        confidence = self._extract_first_float(
            data,
            (
                ('confidence',),
                ('score',),
                ('result', 'confidence'),
                ('result', 'score'),
                ('output', 'confidence'),
                ('output', 'score'),
                ('data', 'confidence'),
                ('data', 'score'),
                ('predictions', 0, 'confidence'),
                ('predictions', 0, 'score'),
            ),
        )
        detected_language = self._extract_first_string(
            data,
            (
                ('language',),
                ('language_code',),
                ('result', 'language'),
                ('result', 'language_code'),
                ('output', 'language'),
                ('output', 'language_code'),
                ('data', 'language'),
                ('data', 'language_code'),
                ('predictions', 0, 'language'),
                ('predictions', 0, 'language_code'),
            ),
        ) or default_language
        return transcript, confidence, detected_language

    def _extract_first_string(self, data: Any, paths: tuple[tuple[Any, ...], ...]) -> str:
        for path in paths:
            value = self._get_nested_value(data, path)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ''

    def _extract_first_float(self, data: Any, paths: tuple[tuple[Any, ...], ...]) -> float:
        for path in paths:
            value = self._get_nested_value(data, path)
            try:
                if value is not None and value != '':
                    return float(value)
            except (TypeError, ValueError):
                continue
        return 0.0

    def _get_nested_value(self, data: Any, path: tuple[Any, ...]) -> Any:
        current = data
        for part in path:
            if isinstance(current, dict):
                if part not in current:
                    return None
                current = current[part]
            elif isinstance(current, list) and isinstance(part, int):
                if part >= len(current):
                    return None
                current = current[part]
            else:
                return None
        return current

    def _log_provider_response(self, provider: str, payload: Dict[str, Any]) -> None:
        preview = self._sanitize_payload_preview(payload)
        asr_logger.info('ASR provider=%s response=%s', provider, preview)

    def _log_http_error(self, provider: str, response) -> None:
        asr_logger.warning(
            'ASR provider=%s request_failed status=%s body=%s',
            provider,
            getattr(response, 'status_code', None),
            self._safe_response_text(response),
        )

    def _safe_response_text(self, response) -> str:
        if response is None:
            return ''
        try:
            text = response.text or ''
        except Exception:
            return '<unavailable>'
        return text[:1000]

    def _sanitize_payload_preview(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            sanitized = {}
            for key, value in payload.items():
                if key in {'audio', 'audio_base64', 'audio_bytes'}:
                    sanitized[key] = '<redacted-audio>'
                else:
                    sanitized[key] = self._sanitize_payload_preview(value)
            return sanitized
        if isinstance(payload, list):
            return [self._sanitize_payload_preview(item) for item in payload[:5]]
        if isinstance(payload, str) and len(payload) > 500:
            return f'{payload[:500]}...'
        return payload
