import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peminjaman', '0011_restore_rejected_status'),
        ('pengguna', '0016_rename_pengguna_sc_npsn_36628f_idx_pengguna_sc_npsn_495644_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='peminjamantransaksi',
            name='risiko',
            field=models.CharField(
                choices=[('normal', 'Normal'), ('rusak', 'Pernah rusak'), ('hilang', 'Pernah hilang')],
                default='normal',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='peminjamantransaksi',
            name='tanggal_dikembalikan',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='PengajuanPerpanjangan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tanggal_kembali_sebelumnya', models.DateField()),
                ('tanggal_kembali_diminta', models.DateField()),
                ('tanggal_kembali_disetujui', models.DateField(blank=True, null=True)),
                ('alasan', models.TextField()),
                ('status', models.CharField(choices=[('diajukan', 'Menunggu persetujuan'), ('disetujui', 'Disetujui'), ('ditolak', 'Ditolak')], default='diajukan', max_length=12)),
                ('catatan_peninjau', models.TextField(blank=True)),
                ('ditinjau_pada', models.DateTimeField(blank=True, null=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('diajukan_oleh', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pengajuan_perpanjangan_peminjaman', to='pengguna.pengguna')),
                ('ditinjau_oleh', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pengajuan_perpanjangan_ditinjau', to='pengguna.pengguna')),
                ('transaksi', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pengajuan_perpanjangan', to='peminjaman.peminjamantransaksi')),
            ],
            options={
                'verbose_name': 'Pengajuan Perpanjangan Peminjaman',
                'verbose_name_plural': 'Pengajuan Perpanjangan Peminjaman',
                'ordering': ['-dibuat_pada'],
            },
        ),
        migrations.CreateModel(
            name='PengingatPeminjaman',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tanggal', models.DateField()),
                ('jenis', models.CharField(choices=[('jatuh_tempo', 'Jatuh tempo'), ('terlambat', 'Terlambat')], max_length=15)),
                ('dikirim_pada', models.DateTimeField(auto_now_add=True)),
                ('transaksi', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pengingat_email', to='peminjaman.peminjamantransaksi')),
            ],
            options={
                'verbose_name': 'Pengingat Peminjaman',
                'verbose_name_plural': 'Pengingat Peminjaman',
            },
        ),
        migrations.AddConstraint(
            model_name='pengingatpeminjaman',
            constraint=models.UniqueConstraint(fields=('transaksi', 'tanggal', 'jenis'), name='unique_pengingat_peminjaman_harian'),
        ),
    ]
