"""
ASGI config for crop_predication_chatbot project.
"""

import os

from crop_predication_chatbot.env import load_env_file
from django.core.asgi import get_asgi_application

load_env_file()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crop_predication_chatbot.settings')

from home.services.realtime_audio_gateway import application as realtime_audio_gateway

django_asgi_app = get_asgi_application()


async def application(scope, receive, send):
    if scope['type'] == 'websocket' and scope.get('path', '').startswith('/ws/voice-assistant/'):
        await realtime_audio_gateway(scope, receive, send)
        return

    await django_asgi_app(scope, receive, send)
