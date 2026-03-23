import logging
import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from crop_predication_chatbot.jwt_utils import JwtError, JwtExpiredError, build_access_token, decode_jwt
from home.models import userProfile

security_logger = logging.getLogger('security')
api_logger = logging.getLogger('api_security')
websocket_logger = logging.getLogger('websocket_security')


def is_password_hash(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith(('pbkdf2_', 'argon2$', 'bcrypt$', 'scrypt$'))


def issue_user_token(user: userProfile) -> str:
    return build_access_token(
        subject=user.email,
        role='user',
        extra_claims={
            'email': user.email,
            'name': user.name,
            'status': user.status,
        },
    )


def issue_admin_token(username: str) -> str:
    return build_access_token(
        subject=username,
        role='admin',
        extra_claims={'username': username},
    )


def get_bearer_token(request) -> str | None:
    auth_header = request.META.get('HTTP_AUTHORIZATION', '').strip()
    if not auth_header.lower().startswith('bearer '):
        return None
    return auth_header.split(' ', 1)[1].strip()


def authenticate_request(request):
    if getattr(request, 'auth_context', None):
        return request.auth_context

    token = get_bearer_token(request)
    if token:
        try:
            claims = decode_jwt(token)
        except JwtExpiredError as exc:
            api_logger.warning('Expired JWT rejected for path=%s ip=%s', request.path, get_client_ip(request))
            raise PermissionError(str(exc)) from exc
        except JwtError as exc:
            api_logger.warning('Invalid JWT rejected for path=%s ip=%s', request.path, get_client_ip(request))
            raise PermissionError(str(exc)) from exc

        request.auth_context = claims
        if claims.get('role') == 'user':
            request.auth_user = userProfile.objects.filter(email__iexact=claims.get('email', '')).first()
        return claims

    if request.session.get('admin_authenticated'):
        claims = {'role': 'admin', 'sub': request.session.get('admin_username')}
        request.auth_context = claims
        return claims

    email = request.session.get('email')
    if email:
        user = userProfile.objects.filter(email__iexact=email).first()
        if user:
            claims = {'role': 'user', 'sub': user.email, 'email': user.email}
            request.auth_context = claims
            request.auth_user = user
            return claims

    raise PermissionError('Authentication required.')


def require_auth(
    *,
    api: bool = False,
    roles: tuple[str, ...] = ('user', 'admin'),
    redirect_to: str = 'userlogin',
):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                claims = authenticate_request(request)
            except PermissionError as exc:
                if api:
                    return JsonResponse({'error': str(exc)}, status=401)
                return redirect(redirect_to)

            role = claims.get('role')
            if role not in roles:
                api_logger.warning(
                    'Role denied for path=%s role=%s ip=%s',
                    request.path,
                    role,
                    get_client_ip(request),
                )
                if api:
                    return JsonResponse({'error': 'Permission denied.'}, status=403)
                return redirect(reverse(redirect_to))

            if role == 'user':
                user = getattr(request, 'auth_user', None)
                if not user or user.status.lower() != 'activated':
                    if api:
                        return JsonResponse({'error': 'Active account required.'}, status=403)
                    return redirect(redirect_to)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def rate_limit(*, key_prefix: str, limit: int, window_seconds: int):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            identifier = _rate_limit_identifier(request, key_prefix)
            cache_key = f'rl:{key_prefix}:{identifier}:{int(time.time() // window_seconds)}'
            try:
                request_count = cache.incr(cache_key)
            except ValueError:
                cache.set(cache_key, 1, timeout=window_seconds)
                request_count = 1

            if request_count == 1:
                cache.expire(cache_key, window_seconds) if hasattr(cache, 'expire') else None

            if request_count > limit:
                api_logger.warning(
                    'Rate limit exceeded for path=%s identifier=%s ip=%s',
                    request.path,
                    identifier,
                    get_client_ip(request),
                )
                return JsonResponse({'error': 'Rate limit exceeded. Please retry later.'}, status=429)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def _rate_limit_identifier(request, key_prefix: str) -> str:
    if getattr(request, 'auth_context', None):
        return request.auth_context.get('sub') or get_client_ip(request)
    token = get_bearer_token(request)
    if token:
        return f'token:{token[:20]}'
    return get_client_ip(request)


def get_client_ip(request) -> str:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


class SessionSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        idle_timeout = int(settings.SESSION_IDLE_TIMEOUT_SECONDS)
        last_activity = request.session.get('last_activity')
        current_time = int(time.time())

        if last_activity and (current_time - int(last_activity)) > idle_timeout:
            had_auth = request.session.get('email') or request.session.get('admin_authenticated')
            request.session.flush()
            if had_auth:
                security_logger.info('Expired idle session for ip=%s path=%s', get_client_ip(request), request.path)

        request.session['last_activity'] = current_time
        request.session.set_expiry(idle_timeout)
        return self.get_response(request)


class JwtAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = get_bearer_token(request)
        if token:
            try:
                claims = decode_jwt(token)
                request.auth_context = claims
                if claims.get('role') == 'user':
                    request.auth_user = userProfile.objects.filter(
                        email__iexact=claims.get('email', '')
                    ).first()
            except JwtExpiredError:
                api_logger.warning('Expired JWT seen at path=%s ip=%s', request.path, get_client_ip(request))
            except JwtError:
                api_logger.warning('Invalid JWT seen at path=%s ip=%s', request.path, get_client_ip(request))

        return self.get_response(request)
