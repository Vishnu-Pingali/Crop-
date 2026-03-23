"""
WSGI config for recommend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from crop_predication_chatbot.env import load_env_file
from django.core.wsgi import get_wsgi_application

load_env_file()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crop_predication_chatbot.settings')

application = get_wsgi_application()
