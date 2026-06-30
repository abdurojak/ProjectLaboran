from django.db import migrations


def backfill_transaksi(apps, schema_editor):
    PeminjamanAlat = apps.get_model('peminjaman', 'PeminjamanAlat')
    PeminjamanTransaksi = apps.get_model('peminjaman', 'PeminjamanTransaksi')

    kode_list = (
        PeminjamanAlat.objects.filter(transaksi__isnull=True)
        .exclude(kode_pinjam='')
        .values_list('kode_pinjam', flat=True)
        .distinct()
    )

    for kode_pinjam in kode_list:
        detail = PeminjamanAlat.objects.filter(kode_pinjam=kode_pinjam).order_by('id').first()
        if not detail:
            continue

        transaksi = PeminjamanTransaksi.objects.create(
            kode_pinjam=kode_pinjam,
            nama_peminjam=detail.nama_peminjam,
            nim=detail.nim,
            no_hp=detail.no_hp,
            tanggal_pinjam=detail.tanggal_pinjam,
            tanggal_kembali=detail.tanggal_kembali,
            catatan=detail.catatan,
        )
        PeminjamanAlat.objects.filter(kode_pinjam=kode_pinjam).update(transaksi=transaksi)


class Migration(migrations.Migration):

    dependencies = [
        ('peminjaman', '0008_peminjamantransaksi_alter_peminjamanalat_kode_pinjam_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_transaksi, migrations.RunPython.noop),
    ]
