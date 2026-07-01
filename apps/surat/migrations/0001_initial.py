import django.db.models.deletion
from django.db import migrations, models

import apps.surat.models


class Migration(migrations.Migration):
    initial = True
    dependencies = [('pengguna', '0013_pengguna_cover_image')]
    operations = [
        migrations.CreateModel(
            name='SuratPengadaan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nomor', models.CharField(max_length=120)), ('tanggal', models.DateField()),
                ('hal', models.CharField(default='Permohonan Pengadaan Kebutuhan Fasilitas Lab. Sistem dan Keamanan Informasi', max_length=200)),
                ('lampiran', models.CharField(default='1 Berkas', max_length=80)),
                ('tujuan_jabatan', models.CharField(default='Wakil Dekan II', max_length=150)),
                ('tujuan_instansi', models.CharField(default='Fakultas Teknologi Industri\nUniversitas Trisakti Jakarta', max_length=200)),
                ('isi', models.TextField()), ('items', models.JSONField(default=apps.surat.models.default_items)),
                ('nama_penandatangan', models.CharField(default='Ir. Gatot Budi Santoso, M.Kom', max_length=150)),
                ('jabatan_penandatangan', models.CharField(default='Kepala Laboratorium', max_length=150)),
                ('laboratorium', models.CharField(default='Sistem dan Keamanan Informasi', max_length=150)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)), ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('dibuat_oleh', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='surat_pengadaan', to='pengguna.pengguna')),
            ],
            options={'verbose_name': 'Surat Pengadaan', 'verbose_name_plural': 'Surat Pengadaan', 'ordering': ['-tanggal', '-id']},
        ),
    ]
