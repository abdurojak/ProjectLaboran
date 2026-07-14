from .models import PesertaPraktikum


def link_peserta_praktikum_to_pengguna(pengguna):
    if not pengguna:
        return 0
    return PesertaPraktikum.objects.filter(
        nim=pengguna.nim_nik,
        pengguna__isnull=True,
    ).update(pengguna=pengguna)
