from django.shortcuts import redirect
from django.urls import resolve, reverse

from .models import Pengguna


class PenggunaLoginRequiredMiddleware:
    MAHASISWA_ALLOWED_NAMESPACES = {'dashboard', 'peminjaman', 'jadwal', 'pengguna'}
    MAHASISWA_ALLOWED_PENGGUNA_PATHS = {'/pengguna/logout/'}

    EXEMPT_PREFIXES = (
        '/admin/',
        '/media/',
        '/static/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        login_url = reverse('pengguna:login')
        register_url = reverse('pengguna:register')
        path = request.path

        is_exempt = (
            path in [login_url, register_url]
            or any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES)
        )

        pengguna_id = request.session.get('pengguna_id')

        if not pengguna_id and not is_exempt:
            return redirect(f'{login_url}?next={path}')

        if pengguna_id and not is_exempt:
            try:
                pengguna = Pengguna.objects.get(pk=pengguna_id)
            except Pengguna.DoesNotExist:
                request.session.pop('pengguna_id', None)
                return redirect(f'{login_url}?next={path}')

            request.current_pengguna = pengguna
            namespace = resolve(path).namespace
            if pengguna.role == 'mahasiswa' and not self.mahasiswa_can_access(namespace, path):
                return redirect('dashboard:home')

        return self.get_response(request)

    def mahasiswa_can_access(self, namespace, path):
        if namespace != 'pengguna':
            return namespace in self.MAHASISWA_ALLOWED_NAMESPACES

        return path in self.MAHASISWA_ALLOWED_PENGGUNA_PATHS
