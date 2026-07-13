from apps.inventaris.models import Barang


def sync_barang_after_peminjaman_status(peminjaman, next_status):
    barang = peminjaman.barang
    if not barang:
        return

    updated_fields = []

    if next_status == 'rusak' and barang.kondisi == 'baik':
        barang.kondisi = 'rusak_ringan'
        updated_fields.append('kondisi')
    elif next_status == 'digantikan' and barang.kondisi != 'baik':
        barang.kondisi = 'baik'
        updated_fields.append('kondisi')

    if updated_fields:
        updated_fields.append('diperbarui_pada')
        barang.save(update_fields=updated_fields)


def update_peminjaman_status(peminjaman, next_status):
    if peminjaman.status == next_status:
        return False

    sync_barang_after_peminjaman_status(peminjaman, next_status)
    peminjaman.status = next_status
    peminjaman.save(update_fields=['status', 'diperbarui_pada'])
    return True
