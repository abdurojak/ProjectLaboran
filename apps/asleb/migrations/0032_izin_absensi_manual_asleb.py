import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('asleb', '0031_asleb_level_diatur_oleh_asleb_level_diatur_pada_and_more'),
        ('jadwal', '0006_permintaanperubahanjadwal'),
        ('pengguna', '0016_rename_pengguna_sc_npsn_36628f_idx_pengguna_sc_npsn_495644_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='IzinAbsensiManualAsleb',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tanggal_praktikum', models.DateField()),
                ('berlaku_sampai', models.DateTimeField()),
                ('alasan', models.CharField(max_length=300)),
                ('digunakan_pada', models.DateTimeField(blank=True, null=True)),
                ('dibatalkan_pada', models.DateTimeField(blank=True, null=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('asleb', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='izin_absensi_manual', to='asleb.asleb')),
                ('dibuka_oleh', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='izin_absensi_manual_dibuka', to='pengguna.pengguna')),
                ('jadwal', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='izin_absensi_manual_asleb', to='jadwal.jadwalpraktikum')),
            ],
            options={
                'verbose_name': 'Izin Absensi Manual Aslab',
                'verbose_name_plural': 'Izin Absensi Manual Aslab',
                'ordering': ['-dibuat_pada'],
            },
        ),
        migrations.AddField(
            model_name='absensiasleb',
            name='izin_manual',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='absensi', to='asleb.izinabsensimanualasleb'),
        ),
    ]
