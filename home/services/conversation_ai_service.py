import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

import requests

from home.models import VoiceConversationSession, VoiceConversationTurn, userProfile

from .crop_prediction_service import CropPredictionService
from .language_processing_service import LanguageAnalysis, LanguageProcessingService
from .text_to_speech_service import TextToSpeechService


@dataclass
class AssistantTurnResult:
    transcript: str
    normalized_text: str
    intent: str
    parameters: Dict[str, float] = field(default_factory=dict)
    missing_parameters: list[str] = field(default_factory=list)
    prediction: str = ''
    class_probabilities: Dict[str, float] = field(default_factory=dict)
    assistant_text: str = ''
    audio_base64: str = ''
    audio_url: str = ''
    asr_confidence: Optional[float] = None
    low_confidence: bool = False
    fallback_to_text: bool = False
    model_metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationAIService:
    def __init__(self) -> None:
        self.language_service = LanguageProcessingService()
        self.crop_service = CropPredictionService()
        self.tts_service = TextToSpeechService()
        self.endpoint = os.getenv('CONVERSATION_AI_API_URL', '').strip() or 'https://integrate.api.nvidia.com/v1/chat/completions'
        self.api_key = os.getenv('CONVERSATION_AI_API_KEY', '').strip() or os.getenv('NVIDIA_API_KEY', '').strip()
        self.model = os.getenv('CONVERSATION_AI_MODEL', 'meta/llama-3.1-8b-instruct')
        self.system_prompt = (
            "You are a precision agriculture assistant for Telugu-speaking farmers. "
            "Respond in clear Telugu, keep advice practical, and reference detected farm parameters when available."
        )

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def get_or_create_session(self, session_id: str, user: userProfile) -> VoiceConversationSession:
        session, _ = VoiceConversationSession.objects.get_or_create(
            session_id=session_id,
            defaults={
                'user': user,
                'language': 'te-IN',
                'channel': 'voice',
                'title': 'AI Crop Assistant Session',
            },
        )
        if session.user_id != user.id:
            session.user = user
            session.save(update_fields=['user', 'updated_at'])
        return session

    def process_user_text(
        self,
        session: VoiceConversationSession,
        text: str,
        source: str = 'text',
        language: str = 'te-IN',
        asr_confidence: Optional[float] = None,
        model_metadata: Optional[Dict[str, Any]] = None,
    ) -> AssistantTurnResult:
        analysis = self.language_service.analyze(text, language=language)
        missing = self.language_service.missing_parameter_labels(analysis.parameters)

        VoiceConversationTurn.objects.create(
            session=session,
            role='user',
            message_text=text,
            normalized_text=analysis.normalized_text,
            source=source,
            language=language,
            asr_confidence=asr_confidence,
            intent=analysis.intent,
            extracted_parameters=analysis.parameters,
            model_metadata=model_metadata or {},
        )

        prediction = ''
        probabilities: Dict[str, float] = {}
        if analysis.asks_prediction and self.language_service.is_complete_parameter_set(analysis.parameters):
            crop_result = self.crop_service.predict(analysis.parameters)
            if crop_result.ready:
                prediction = crop_result.prediction
                probabilities = crop_result.class_probabilities

        assistant_text = self._generate_reply(analysis, prediction, missing)
        tts_result = self.tts_service.synthesize(assistant_text, language='te-IN')

        VoiceConversationTurn.objects.create(
            session=session,
            role='assistant',
            message_text=assistant_text,
            normalized_text=assistant_text,
            source='tts' if tts_result.audio_base64 else 'text',
            language='te-IN',
            intent=analysis.intent,
            extracted_parameters=analysis.parameters,
            predicted_crop=prediction,
            model_metadata={
                'probabilities': probabilities,
                'tts_provider': tts_result.provider,
                **(model_metadata or {}),
            },
        )

        session.last_asr_confidence = asr_confidence
        session.metadata = {
            **session.metadata,
            'last_intent': analysis.intent,
            'last_parameters': analysis.parameters,
            'last_prediction': prediction,
        }
        session.save(update_fields=['last_asr_confidence', 'metadata', 'updated_at'])

        return AssistantTurnResult(
            transcript=text,
            normalized_text=analysis.normalized_text,
            intent=analysis.intent,
            parameters=analysis.parameters,
            missing_parameters=missing,
            prediction=prediction,
            class_probabilities=probabilities,
            assistant_text=assistant_text,
            audio_base64=tts_result.audio_base64,
            audio_url=tts_result.audio_url,
            asr_confidence=asr_confidence,
            model_metadata={
                'analysis': asdict(analysis),
                'tts_provider': tts_result.provider,
                'tts_voice': tts_result.voice,
                **(model_metadata or {}),
            },
        )

    def build_low_confidence_reply(
        self,
        session: VoiceConversationSession,
        prompt_text: str,
        confidence: float,
        model_metadata: Optional[Dict[str, Any]] = None,
    ) -> AssistantTurnResult:
        assistant_text = (
            "మీ మాట పూర్తిగా స్పష్టంగా వినిపించలేదు. దయచేసి మళ్లీ నెమ్మదిగా మాట్లాడండి లేదా కింద ఉన్న టెక్స్ట్ బాక్స్‌లో మీ వివరాలు టైప్ చేయండి."
        )
        VoiceConversationTurn.objects.create(
            session=session,
            role='system',
            message_text=prompt_text,
            normalized_text=prompt_text,
            source='asr-low-confidence',
            language='te-IN',
            asr_confidence=confidence,
            intent='fallback_to_text',
            model_metadata=model_metadata or {},
        )
        return AssistantTurnResult(
            transcript='',
            normalized_text='',
            intent='fallback_to_text',
            assistant_text=assistant_text,
            asr_confidence=confidence,
            low_confidence=True,
            fallback_to_text=True,
            model_metadata=model_metadata or {},
        )

    def _generate_reply(self, analysis: LanguageAnalysis, prediction: str, missing_parameters: list[str]) -> str:
        if self.api_key:
            generated = self._generate_reply_with_remote_ai(analysis, prediction, missing_parameters)
            if generated:
                return generated

        if analysis.intent == 'crop_prediction':
            if prediction:
                return (
                    f"మీరు ఇచ్చిన మట్టి మరియు వాతావరణ వివరాల ఆధారంగా సరైన పంట {prediction}. "
                    "ఈ పంటకు సమతుల్య ఎరువుల వినియోగం, మట్టిలో తేమ నిర్వహణ, మరియు స్థానిక వాతావరణాన్ని గమనించడం మంచిది."
                )
            if missing_parameters:
                missing_text = ", ".join(missing_parameters)
                return f"పంట సిఫారసు ఇవ్వడానికి ఇంకా ఈ వివరాలు కావాలి: {missing_text}. దయచేసి ఒక్కో విలువను చెప్పండి."
            return "పంట సిఫారసు కోసం మట్టి మరియు వాతావరణ విలువలను చెప్పండి."

        if analysis.intent == 'farming_guidance':
            return (
                "మట్టిలో పోషక సమతుల్యత, నీటి నిర్వహణ, మరియు స్థానిక వాతావరణాన్ని కలిపి చూసి నిర్ణయం తీసుకోవాలి. "
                "మీరు ఇష్టపడితే N, P, K, ఉష్ణోగ్రత, ఆర్ద్రత, pH, వర్షపాతం విలువలు చెబితే నేను పంటను కూడా సూచిస్తాను."
            )

        return (
            "నమస్కారం రైతు మిత్రమా. మట్టి పోషకాలు, ఉష్ణోగ్రత, ఆర్ద్రత, pH, వర్షపాతం గురించి చెప్పండి. "
            "నేను మీకు సరైన పంట మరియు సాగు సూచనలు ఇస్తాను."
        )

    def _generate_reply_with_remote_ai(
        self,
        analysis: LanguageAnalysis,
        prediction: str,
        missing_parameters: list[str],
    ) -> str:
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': self.system_prompt},
                {
                    'role': 'user',
                    'content': (
                        f"Language: te-IN\n"
                        f"User text: {analysis.raw_text}\n"
                        f"Normalized text: {analysis.normalized_text}\n"
                        f"Intent: {analysis.intent}\n"
                        f"Parameters: {analysis.parameters}\n"
                        f"Missing parameters: {missing_parameters}\n"
                        f"Prediction: {prediction}\n"
                        "Respond in Telugu for a farmer."
                    ),
                },
            ],
            'temperature': 0.3,
            'max_tokens': 300,
        }
        try:
            response = requests.post(self.endpoint, json=payload, headers=headers, timeout=45)
            response.raise_for_status()
            data = response.json()
            if 'choices' in data and data['choices']:
                return data['choices'][0].get('message', {}).get('content', '')
            return data.get('response_text', '')
        except requests.RequestException:
            return ''
