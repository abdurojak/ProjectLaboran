from .models import PesertaPraktikum


def link_peserta_praktikum_to_pengguna(pengguna):
    if not pengguna or not getattr(pengguna, 'nim_nik', None):
        return 0
    nim = pengguna.nim_nik.strip()
    if not nim:
        return 0
    return PesertaPraktikum.objects.filter(
        nim=nim,
        pengguna__isnull=True,
    ).update(pengguna=pengguna)
