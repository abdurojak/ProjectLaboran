import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('asleb', '0023_jadwal_absensi_set_null'),
        ('pendaftaran_asleb', '0015_riwayatasleb_and_more'),
        ('pengguna', '0015_school_pengalaman_pendidikan_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='TugasLaporanPraktikum',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('judul', models.CharField(max_length=200)),
                ('pertemuan', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('deskripsi', models.TextField(blank=True)),
                ('format_file', models.CharField(default='pdf,doc,docx', max_length=120)),
                ('ukuran_maksimal_mb', models.PositiveSmallIntegerField(default=10)),
                ('mulai_pengumpulan', models.DateTimeField(default=django.utils.timezone.now)),
                ('batas_pengumpulan', models.DateTimeField()),
                ('izinkan_terlambat', models.BooleanField(default=False)),
                ('aktif', models.BooleanField(default=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('asisten_pemeriksa', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tugas_laporan_diperiksa', to='asleb.asleb')),
                ('dibuat_oleh', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tugas_laporan_dibuat', to='pengguna.pengguna')),
                ('matkul', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tugas_laporan', to='pendaftaran_asleb.matakuliahasleb')),
                ('modul', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tugas_laporan', to='asleb.modulpraktikum')),
            ],
            options={
                'verbose_name': 'Tugas Laporan Praktikum',
                'verbose_name_plural': 'Tugas Laporan Praktikum',
                'ordering': ['-batas_pengumpulan', 'matkul__nama', 'judul'],
            },
        ),
        migrations.CreateModel(
            name='PengumpulanLaporanPraktikum',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_laporan', models.FileField(upload_to='laporan_praktikum/%Y/%m/')),
                ('nama_file_asli', models.CharField(blank=True, max_length=220)),
                ('file_size', models.PositiveBigIntegerField(blank=True, null=True)),
                ('versi', models.PositiveSmallIntegerField(default=1)),
                ('dikumpulkan_pada', models.DateTimeField(default=django.utils.timezone.now)),
                ('terlambat', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('belum_dikumpulkan', 'Belum dikumpulkan'), ('sudah_dikumpulkan', 'Sudah dikumpulkan'), ('terlambat', 'Terlambat'), ('sedang_diperiksa', 'Sedang diperiksa'), ('perlu_revisi', 'Perlu revisi'), ('sudah_direvisi', 'Sudah direvisi'), ('diterima', 'Diterima'), ('sudah_dinilai', 'Sudah dinilai')], default='sudah_dikumpulkan', max_length=30)),
                ('catatan_asisten', models.TextField(blank=True)),
                ('nilai', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('diperiksa_pada', models.DateTimeField(blank=True, null=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('diperiksa_oleh', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='laporan_praktikum_diperiksa', to='pengguna.pengguna')),
                ('peserta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pengumpulan_laporan', to='asleb.pesertapraktikum')),
                ('tugas', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pengumpulan', to='asleb.tugaslaporanpraktikum')),
            ],
            options={
                'verbose_name': 'Pengumpulan Laporan Praktikum',
                'verbose_name_plural': 'Pengumpulan Laporan Praktikum',
                'ordering': ['-dikumpulkan_pada'],
            },
        ),
        migrations.CreateModel(
            name='LogAktivitasPraktikum',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('aksi', models.CharField(max_length=120)),
                ('deskripsi', models.TextField(blank=True)),
                ('matkul_label', models.CharField(blank=True, max_length=250)),
                ('peserta_nim', models.CharField(blank=True, max_length=40)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('pengguna', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='log_aktivitas_praktikum', to='pengguna.pengguna')),
            ],
            options={
                'verbose_name': 'Log Aktivitas Praktikum',
                'verbose_name_plural': 'Log Aktivitas Praktikum',
                'ordering': ['-dibuat_pada'],
            },
        ),
        migrations.AddConstraint(
            model_name='pengumpulanlaporanpraktikum',
            constraint=models.UniqueConstraint(fields=('tugas', 'peserta', 'versi'), name='unique_laporan_tugas_peserta_versi'),
        ),
    ]
