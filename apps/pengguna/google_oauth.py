import base64
import hashlib
import json
import secrets
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import jwt
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache

from .models import Pengguna


SESSION_KEY = 'google_oauth_pending'
AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
JWKS_URL = 'https://www.googleapis.com/oauth2/v3/certs'


def _configured():
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def _callback_uri(request):
    return request.build_absolute_uri(reverse('pengguna:google_callback'))


def _safe_next(request):
    next_url = request.GET.get('next', '')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return next_url
    return reverse('dashboard:home')


@require_GET
@never_cache
def google_login(request):
    if not _configured():
        messages.error(request, 'Login Google belum dikonfigurasi.')
        return redirect('pengguna:login')

    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    request.session[SESSION_KEY] = {
        'state': state,
        'nonce': nonce,
        'verifier': verifier,
        'next': _safe_next(request),
        'created': time.time(),
    }
    params = {
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'redirect_uri': _callback_uri(request),
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'nonce': nonce,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'prompt': 'select_account',
    }
    return redirect(f'{AUTH_URL}?{urlencode(params)}')


@require_GET
@never_cache
def google_callback(request):
    pending = request.session.pop(SESSION_KEY, None)
    if (
        not _configured() or not pending or not request.GET.get('code')
        or not secrets.compare_digest(request.GET.get('state', ''), pending['state'])
        or time.time() - pending['created'] > 600
    ):
        messages.error(request, 'Sesi login Google tidak valid atau telah kedaluwarsa. Coba lagi.')
        return redirect('pengguna:login')

    payload = urlencode({
        'code': request.GET['code'],
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
        'redirect_uri': _callback_uri(request),
        'grant_type': 'authorization_code',
        'code_verifier': pending['verifier'],
    }).encode()
    try:
        token_request = Request(TOKEN_URL, data=payload, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urlopen(token_request, timeout=10) as response:
            token = json.load(response)['id_token']
        claims = jwt.decode(
            token,
            jwt.PyJWKClient(JWKS_URL).get_signing_key_from_jwt(token).key,
            algorithms=['RS256'],
            audience=settings.GOOGLE_OAUTH_CLIENT_ID,
            issuer=['https://accounts.google.com', 'accounts.google.com'],
        )
    except (URLError, TimeoutError, ValueError, KeyError, jwt.PyJWTError):
        messages.error(request, 'Verifikasi Google gagal. Silakan coba kembali.')
        return redirect('pengguna:login')

    if (
        not secrets.compare_digest(str(claims.get('nonce', '')), pending['nonce'])
        or claims.get('email_verified') is not True
        or not claims.get('email')
    ):
        messages.error(request, 'Email Google belum terverifikasi atau respons login tidak valid.')
        return redirect('pengguna:login')

    pengguna = Pengguna.objects.filter(email__iexact=claims['email']).first()
    if not pengguna or not pengguna.is_verified:
        messages.error(request, 'Email Google belum terhubung ke akun LabHub yang aktif.')
        return redirect('pengguna:login')

    request.session.cycle_key()
    request.session['pengguna_id'] = pengguna.pk
    if pengguna.role == 'laboran' and pengguna.must_change_password:
        request.session['password_change_required'] = True
        return redirect('pengguna:force_password_change')
    messages.success(request, f'Selamat datang, {pengguna.nama_pengguna}.')
    return redirect(pending['next'])
