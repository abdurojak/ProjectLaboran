from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from apps.pengguna.models import Pengguna
from apps.asleb.models import Asleb
from apps.pendaftaran_asleb.services import sync_expired_asleb_periods

from .jwt_service import decode_token


class PenggunaJWTAuthentication(BaseAuthentication):
    keyword = b'bearer'

    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header:
            return None
        if len(header) != 2 or header[0].lower() != self.keyword:
            raise AuthenticationFailed('Gunakan header Authorization: Bearer <token>.')
        try:
            raw_token = header[1].decode('utf-8')
        except UnicodeError as exc:
            raise AuthenticationFailed('Token tidak valid.') from exc
        payload = decode_token(raw_token, 'access')
        pengguna = Pengguna.objects.filter(pk=payload['sub'], is_verified=True).first()
        if not pengguna:
            raise AuthenticationFailed('Akun tidak ditemukan atau belum diverifikasi.')
        sync_expired_asleb_periods()
        pengguna.refresh_from_db(fields=['role'])
        if pengguna.role != 'asisten_lab' or not Asleb.objects.filter(nim=pengguna.nim_nik, status='aktif').exists():
            raise AuthenticationFailed('Akses Asisten Lab sudah tidak aktif.')
        return pengguna, payload
