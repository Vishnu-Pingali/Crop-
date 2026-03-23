import base64
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict

import requests
from django.conf import settings


@dataclass
class TTSResult:
    audio_base64: str = ''
    audio_url: str = ''
    provider: str = 'fallback'
    voice: str = ''
    raw: Dict[str, Any] = field(default_factory=dict)


class TextToSpeechService:
    def __init__(self) -> None:
        self.endpoint = os.getenv('NVIDIA_MAGPIE_TTS_URL', '').strip()
        self.api_key = (
            os.getenv('NVIDIA_MAGPIE_API_KEY', '').strip()
            or os.getenv('NVIDIA_API_KEY', '').strip()
        )
        self.function_id = os.getenv('NVIDIA_MAGPIE_FUNCTION_ID', '').strip()
        self.voice = os.getenv('NVIDIA_MAGPIE_VOICE', 'Magpie-Multilingual.Female-1')

    def synthesize(self, text: str, language: str = 'te-IN') -> TTSResult:
        if self.endpoint:
            return self._synthesize_with_nvidia(text, language)

        if self.api_key and self.function_id:
            return self._synthesize_with_nvcf(text, language)

        return TTSResult(
            audio_base64='',
            audio_url='',
            provider='fallback',
            voice='',
            raw={'reason': 'Set NVIDIA_MAGPIE_TTS_URL or NVIDIA_MAGPIE_FUNCTION_ID with NVIDIA_MAGPIE_API_KEY'},
        )

    def _synthesize_with_nvidia(self, text: str, language: str) -> TTSResult:
        payload = {
            'text': text,
            'language_code': language,
            'voice': self.voice,
            'model': 'magpie-multilingual',
        }
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        try:
            response = requests.post(self.endpoint, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            return TTSResult(
                audio_base64='',
                audio_url='',
                provider='fallback',
                voice='',
                raw={'reason': str(exc)},
            )

        if 'audio_base64' in data:
            audio_base64 = data['audio_base64']
        elif 'audio' in data and isinstance(data['audio'], str):
            audio_base64 = data['audio']
        else:
            audio_bytes = data.get('audio_bytes', b'')
            if isinstance(audio_bytes, str):
                audio_base64 = audio_bytes
            else:
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8') if audio_bytes else ''

        audio_url = self._persist_audio(audio_base64)
        return TTSResult(
            audio_base64=audio_base64,
            audio_url=audio_url,
            provider='nvidia_magpie',
            voice=data.get('voice', self.voice),
            raw=data,
        )

    def _synthesize_with_nvcf(self, text: str, language: str) -> TTSResult:
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        payload = {
            'text': text,
            'language_code': language,
            'voice': self.voice,
        }
        try:
            response = requests.post(
                f'https://api.nvcf.nvidia.com/v2/nvcf/exec/functions/{self.function_id}',
                json=payload,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json() if response.content else {}
        except requests.RequestException as exc:
            return TTSResult(
                audio_base64='',
                audio_url='',
                provider='fallback',
                voice='',
                raw={'reason': str(exc)},
            )
        audio_base64 = data.get('audio_base64', '')
        audio_url = self._persist_audio(audio_base64)
        return TTSResult(
            audio_base64=audio_base64,
            audio_url=audio_url,
            provider='nvidia_nvcf_magpie',
            voice=data.get('voice', self.voice),
            raw=data,
        )

    def is_configured(self) -> bool:
        return bool(self.endpoint or (self.api_key and self.function_id))

    def _persist_audio(self, audio_base64: str) -> str:
        if not audio_base64:
            return ''

        synth_dir = os.path.join(settings.MEDIA_ROOT, 'synth')
        os.makedirs(synth_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.wav"
        file_path = os.path.join(synth_dir, filename)
        with open(file_path, 'wb') as file_obj:
            file_obj.write(base64.b64decode(audio_base64))
        return f"{settings.MEDIA_URL}synth/{filename}"
