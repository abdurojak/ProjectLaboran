from .models import BarangTertinggal


def link_barang_tertinggal_to_pengguna(pengguna):
    if not pengguna or not getattr(pengguna, 'nim_nik', None):
        return 0

    return BarangTertinggal.objects.filter(
        nim_pemilik=pengguna.nim_nik,
        pemilik__isnull=True,
    ).update(pemilik=pengguna)
