"""
Django settings for crop_predication_chatbot project.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .env import get_env, get_env_bool, get_env_list, get_secret, load_env_file

BASE_DIR = Path(__file__).resolve().parent.parent
load_env_file()

APP_ENV = (get_env('APP_ENV', 'development') or 'development').lower()
IS_DEVELOPMENT = APP_ENV == 'development'
IS_STAGING = APP_ENV == 'staging'
IS_PRODUCTION = APP_ENV == 'production'


def _env_int(name: str, default: int) -> int:
    value = get_env(name)
    return int(value) if value is not None else default


def _require_non_empty(name: str, *, allow_in_dev_default: str | None = None) -> str:
    value = get_secret(name, default=allow_in_dev_default if IS_DEVELOPMENT else None)
    if value is None or not str(value).strip():
        raise ImproperlyConfigured(f'Missing required environment variable: {name}')
    return str(value).strip()


SECRET_KEY = _require_non_empty(
    'DJANGO_SECRET_KEY',
    allow_in_dev_default='django-dev-only-change-me',
)
DEBUG = get_env_bool('DJANGO_DEBUG', IS_DEVELOPMENT)
ALLOWED_HOSTS = get_env_list('DJANGO_ALLOWED_HOSTS', ['127.0.0.1', 'localhost'] if IS_DEVELOPMENT else [])
CSRF_TRUSTED_ORIGINS = get_env_list('DJANGO_CSRF_TRUSTED_ORIGINS', [])

if not ALLOWED_HOSTS and not IS_DEVELOPMENT:
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must be configured outside development.')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'home',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'crop_predication_chatbot.security.SessionSecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'crop_predication_chatbot.security.JwtAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'crop_predication_chatbot.urls'
ASGI_APPLICATION = 'crop_predication_chatbot.asgi.application'
WSGI_APPLICATION = 'crop_predication_chatbot.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

database_url = get_env('DATABASE_URL')
if database_url and database_url.startswith('sqlite:///'):
    database_name = database_url.replace('sqlite:///', '', 1)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': database_name,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / get_env('SQLITE_NAME', 'db.sqlite3'),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = get_env('DJANGO_TIME_ZONE', 'Asia/Calcutta')
USE_I18N = True
USE_TZ = False

STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND = get_env('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = get_env('EMAIL_HOST') or get_env('SMTP_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(get_env('EMAIL_PORT') or get_env('SMTP_PORT', '587'))
EMAIL_USE_TLS = get_env_bool('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = get_env_bool('EMAIL_USE_SSL', False)
EMAIL_HOST_USER = get_secret('EMAIL_HOST_USER') or get_secret('SMTP_USERNAME') or get_secret('SMTP_USER') or ''
EMAIL_HOST_PASSWORD = (
    (get_secret('EMAIL_HOST_PASSWORD') or get_secret('SMTP_PASSWORD') or '').replace(' ', '')
)
DEFAULT_FROM_EMAIL = get_env('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'no-reply@localhost')
SERVER_EMAIL = get_env('SERVER_EMAIL', DEFAULT_FROM_EMAIL)
EMAIL_TIMEOUT = _env_int('EMAIL_TIMEOUT', 30)

JWT_SECRET_KEY = get_secret('JWT_SECRET_KEY', SECRET_KEY)
JWT_ACCESS_TTL_SECONDS = _env_int('JWT_ACCESS_TTL_SECONDS', 3600)
JWT_ISSUER = get_env('JWT_ISSUER', 'crop-predication-chatbot')
JWT_AUDIENCE = get_env('JWT_AUDIENCE', 'crop-predication-chatbot-api')

ADMIN_USERNAME = _require_non_empty('ADMIN_USERNAME', allow_in_dev_default='admin')
ADMIN_PASSWORD = get_secret('ADMIN_PASSWORD', 'admin' if IS_DEVELOPMENT else None)
ADMIN_PASSWORD_HASH = get_secret('ADMIN_PASSWORD_HASH')
if not ADMIN_PASSWORD and not ADMIN_PASSWORD_HASH:
    raise ImproperlyConfigured('Set ADMIN_PASSWORD or ADMIN_PASSWORD_HASH in the environment.')

SESSION_IDLE_TIMEOUT_SECONDS = _env_int('SESSION_IDLE_TIMEOUT_SECONDS', 1800)
SESSION_COOKIE_AGE = SESSION_IDLE_TIMEOUT_SECONDS
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = get_env_bool('SESSION_COOKIE_SECURE', IS_STAGING or IS_PRODUCTION)
SESSION_COOKIE_SAMESITE = get_env('SESSION_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = get_env_bool('CSRF_COOKIE_SECURE', IS_STAGING or IS_PRODUCTION)
CSRF_COOKIE_SAMESITE = get_env('CSRF_COOKIE_SAMESITE', 'Lax')
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = get_env_bool('SECURE_SSL_REDIRECT', IS_PRODUCTION)
SECURE_HSTS_SECONDS = _env_int('SECURE_HSTS_SECONDS', 31536000 if IS_PRODUCTION else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', IS_PRODUCTION)
SECURE_HSTS_PRELOAD = get_env_bool('SECURE_HSTS_PRELOAD', IS_PRODUCTION)

FILE_UPLOAD_MAX_MEMORY_SIZE = _env_int('FILE_UPLOAD_MAX_MEMORY_SIZE', 5 * 1024 * 1024)
DATA_UPLOAD_MAX_MEMORY_SIZE = _env_int('DATA_UPLOAD_MAX_MEMORY_SIZE', 10 * 1024 * 1024)
FILE_UPLOAD_PERMISSIONS = 0o640

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'crop-predication-chatbot-security',
    }
}

VOICE_ASSISTANT_CONFIG = {
    'asr_confidence_threshold': float(get_env('VOICE_ASR_CONFIDENCE_THRESHOLD', '0.55')),
    'nvidia_parakeet_api_key': get_secret('NVIDIA_PARAKEET_API_KEY') or get_secret('NVIDIA_API_KEY', ''),
    'nvidia_parakeet_asr_url': get_env('NVIDIA_PARAKEET_ASR_URL', ''),
    'nvidia_parakeet_function_id': get_env('NVIDIA_PARAKEET_FUNCTION_ID', ''),
    'nvidia_magpie_api_key': get_secret('NVIDIA_MAGPIE_API_KEY') or get_secret('NVIDIA_API_KEY', ''),
    'nvidia_magpie_tts_url': get_env('NVIDIA_MAGPIE_TTS_URL', ''),
    'nvidia_magpie_function_id': get_env('NVIDIA_MAGPIE_FUNCTION_ID', ''),
    'conversation_ai_api_key': get_secret('CONVERSATION_AI_API_KEY') or get_secret('NVIDIA_API_KEY', ''),
    'conversation_ai_api_url': get_env(
        'CONVERSATION_AI_API_URL',
        'https://integrate.api.nvidia.com/v1/chat/completions',
    ),
}

VOICE_TEXT_RATE_LIMIT = _env_int('VOICE_TEXT_RATE_LIMIT', 30)
VOICE_AUDIO_RATE_LIMIT = _env_int('VOICE_AUDIO_RATE_LIMIT', 20)
RATE_LIMIT_WINDOW_SECONDS = _env_int('RATE_LIMIT_WINDOW_SECONDS', 60)
WEBSOCKET_CONNECT_RATE_LIMIT = _env_int('WEBSOCKET_CONNECT_RATE_LIMIT', 20)
MAX_PROFILE_UPLOAD_SIZE = _env_int('MAX_PROFILE_UPLOAD_SIZE', 2 * 1024 * 1024)
ALLOWED_PROFILE_IMAGE_EXTENSIONS = get_env_list('ALLOWED_PROFILE_IMAGE_EXTENSIONS', ['.jpg', '.jpeg', '.png', '.gif'])

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'structured': {
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'structured',
        },
    },
    'loggers': {
        'security': {'handlers': ['console'], 'level': get_env('SECURITY_LOG_LEVEL', 'INFO'), 'propagate': False},
        'api_security': {'handlers': ['console'], 'level': get_env('API_SECURITY_LOG_LEVEL', 'INFO'), 'propagate': False},
        'websocket_security': {'handlers': ['console'], 'level': get_env('WEBSOCKET_SECURITY_LOG_LEVEL', 'INFO'), 'propagate': False},
        'django.security': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

if (IS_STAGING or IS_PRODUCTION) and SECRET_KEY == 'django-dev-only-change-me':
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be overridden outside development.')
