import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed


JWT_ALGORITHM = 'HS256'


def create_token(pengguna, token_type):
    now = timezone.now()
    lifetime = (
        timedelta(minutes=settings.MOBILE_JWT_ACCESS_MINUTES)
        if token_type == 'access'
        else timedelta(days=settings.MOBILE_JWT_REFRESH_DAYS)
    )
    payload = {
        'sub': str(pengguna.pk),
        'role': pengguna.role,
        'type': token_type,
        'iat': now,
        'exp': now + lifetime,
        'jti': uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_token_pair(pengguna):
    return {
        'access': create_token(pengguna, 'access'),
        'refresh': create_token(pengguna, 'refresh'),
        'access_expires_in': settings.MOBILE_JWT_ACCESS_MINUTES * 60,
    }


def decode_token(token, expected_type):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationFailed('Token sudah kedaluwarsa.') from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationFailed('Token tidak valid.') from exc
    if payload.get('type') != expected_type or not payload.get('sub'):
        raise AuthenticationFailed('Jenis token tidak valid.')
    return payload
