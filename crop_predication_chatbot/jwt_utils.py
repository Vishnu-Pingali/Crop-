import base64
import hashlib
import hmac
import json
import time
from typing import Any

from django.conf import settings


class JwtError(Exception):
    pass


class JwtExpiredError(JwtError):
    pass


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _b64url_decode(value: str) -> bytes:
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(f'{value}{padding}')


def _sign(message: bytes) -> str:
    signature = hmac.new(
        settings.JWT_SECRET_KEY.encode('utf-8'),
        message,
        hashlib.sha256,
    ).digest()
    return _b64url_encode(signature)


def encode_jwt(payload: dict[str, Any]) -> str:
    header = {'alg': 'HS256', 'typ': 'JWT'}
    encoded_header = _b64url_encode(
        json.dumps(header, separators=(',', ':')).encode('utf-8')
    )
    encoded_payload = _b64url_encode(
        json.dumps(payload, separators=(',', ':')).encode('utf-8')
    )
    signing_input = f'{encoded_header}.{encoded_payload}'.encode('ascii')
    return f'{encoded_header}.{encoded_payload}.{_sign(signing_input)}'


def decode_jwt(token: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split('.')
    except ValueError as exc:
        raise JwtError('Malformed token.') from exc

    signing_input = f'{encoded_header}.{encoded_payload}'.encode('ascii')
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(expected_signature, encoded_signature):
        raise JwtError('Invalid token signature.')

    try:
        payload = json.loads(_b64url_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise JwtError('Invalid token payload.') from exc

    expires_at = int(payload.get('exp', 0) or 0)
    if expires_at and expires_at < int(time.time()):
        raise JwtExpiredError('Token expired.')
    return payload


def build_access_token(
    *,
    subject: str,
    role: str,
    token_type: str = 'access',
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = int(time.time())
    payload = {
        'sub': subject,
        'role': role,
        'type': token_type,
        'iat': now,
        'exp': now + int(settings.JWT_ACCESS_TTL_SECONDS),
        'iss': settings.JWT_ISSUER,
        'aud': settings.JWT_AUDIENCE,
    }
    if extra_claims:
        payload.update(extra_claims)
    return encode_jwt(payload)
