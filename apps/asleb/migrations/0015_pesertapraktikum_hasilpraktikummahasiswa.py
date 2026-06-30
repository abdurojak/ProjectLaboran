import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('asleb', '0014_absensiasleb_bukti_foto'),
        ('pendaftaran_asleb', '0011_seed_kode_mk_sks'),
        ('pengguna', '0010_pengguna_cv'),
    ]

    operations = [
        migrations.CreateModel(
            name='PesertaPraktikum',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nim', models.CharField(max_length=40, verbose_name='NIM')),
                ('nama', models.CharField(max_length=150)),
                ('aktif', models.BooleanField(default=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('dibuat_oleh', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='peserta_praktikum_dibuat', to='pengguna.pengguna')),
                ('matkul', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='peserta_praktikum', to='pendaftaran_asleb.matakuliahasleb')),
                ('pengguna', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kelas_praktikum', to='pengguna.pengguna')),
            ],
            options={'verbose_name': 'Peserta Praktikum', 'verbose_name_plural': 'Peserta Praktikum', 'ordering': ['matkul__nama', 'matkul__kelas', 'nama']},
        ),
        migrations.CreateModel(
            name='HasilPraktikumMahasiswa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tanggal_praktikum', models.DateField(default=django.utils.timezone.localdate)),
                ('status_absensi', models.CharField(choices=[('hadir', 'Hadir'), ('izin', 'Izin'), ('sakit', 'Sakit'), ('alpa', 'Alpa')], default='hadir', max_length=12)),
                ('nilai', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('catatan', models.CharField(blank=True, max_length=250)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('dicatat_oleh', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='hasil_praktikum_dicatat', to='pengguna.pengguna')),
                ('modul', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='hasil_mahasiswa', to='asleb.modulpraktikum')),
                ('peserta', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='hasil_praktikum', to='asleb.pesertapraktikum')),
            ],
            options={'verbose_name': 'Nilai dan Absensi Mahasiswa', 'verbose_name_plural': 'Nilai dan Absensi Mahasiswa', 'ordering': ['modul__nomor', 'peserta__nama']},
        ),
        migrations.AddConstraint(model_name='pesertapraktikum', constraint=models.UniqueConstraint(fields=('matkul', 'nim'), name='unique_peserta_per_matkul')),
        migrations.AddConstraint(model_name='hasilpraktikummahasiswa', constraint=models.UniqueConstraint(fields=('peserta', 'modul'), name='unique_hasil_peserta_per_modul')),
    ]
