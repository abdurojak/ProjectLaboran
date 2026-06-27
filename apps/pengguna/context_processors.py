from .models import Pengguna


def pengguna_session(request):
    if hasattr(request, 'current_pengguna'):
        return {
            'current_pengguna': request.current_pengguna,
        }

    pengguna_id = request.session.get('pengguna_id')
    pengguna = None

    if pengguna_id:
        try:
            pengguna = Pengguna.objects.get(pk=pengguna_id)
        except Pengguna.DoesNotExist:
            request.session.pop('pengguna_id', None)

    return {
        'current_pengguna': pengguna,
    }
