import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from .models import MobileSession


JWT_ALGORITHM = 'HS256'
JWT_ISSUER = 'labhub-mobile-api'
JWT_AUDIENCE = 'labhub-mobile-app'


def create_token(pengguna, token_type, session_id, *, now=None, jti=None):
    now = now or timezone.now()
    lifetime = (
        timedelta(minutes=settings.MOBILE_JWT_ACCESS_MINUTES)
        if token_type == 'access'
        else timedelta(days=settings.MOBILE_JWT_REFRESH_DAYS)
    )
    payload = {
        'sub': str(pengguna.pk),
        'role': pengguna.role,
        'type': token_type,
        'sid': str(session_id),
        'iat': now,
        'exp': now + lifetime,
        'jti': jti or uuid.uuid4().hex,
        'iss': JWT_ISSUER,
        'aud': JWT_AUDIENCE,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_token_pair(pengguna):
    now = timezone.now()
    refresh_jti = uuid.uuid4().hex
    session = MobileSession.objects.create(
        pengguna=pengguna,
        refresh_jti=refresh_jti,
        expires_at=now + timedelta(days=settings.MOBILE_JWT_REFRESH_DAYS),
    )
    return {
        'access': create_token(pengguna, 'access', session.pk, now=now),
        'refresh': create_token(
            pengguna,
            'refresh',
            session.pk,
            now=now,
            jti=refresh_jti,
        ),
        'access_expires_in': settings.MOBILE_JWT_ACCESS_MINUTES * 60,
    }


def decode_token(token, expected_type):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={'require': ['exp', 'iat', 'jti', 'sub', 'sid', 'type']},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationFailed('Token sudah kedaluwarsa.') from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationFailed('Token tidak valid.') from exc
    if payload.get('type') != expected_type:
        raise AuthenticationFailed('Jenis token tidak valid.')
    return payload


def get_active_session(payload, *, for_update=False, require_refresh_jti=False):
    queryset = MobileSession.objects
    if for_update:
        queryset = queryset.select_for_update()
    try:
        session = queryset.filter(
            pk=payload['sid'],
            pengguna_id=payload['sub'],
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).first()
    except (ValidationError, ValueError, TypeError) as exc:
        raise AuthenticationFailed('Sesi mobile tidak valid.') from exc
    if session is None:
        raise AuthenticationFailed('Sesi mobile sudah berakhir. Silakan login kembali.')
    if require_refresh_jti and session.refresh_jti != payload['jti']:
        raise AuthenticationFailed('Refresh token sudah tidak berlaku.')
    return session


def revoke_session(session):
    if session.revoked_at is None:
        session.revoked_at = timezone.now()
        session.save(update_fields=['revoked_at'])
