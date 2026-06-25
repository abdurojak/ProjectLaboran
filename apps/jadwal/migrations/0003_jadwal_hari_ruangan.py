from django.db import migrations, models
import django.db.models.deletion


DAY_MAP = {
    0: 'senin',
    1: 'selasa',
    2: 'rabu',
    3: 'kamis',
    4: 'jumat',
    5: 'sabtu',
    6: 'senin',
}


def migrate_jadwal_to_hari_ruangan(apps, schema_editor):
    JadwalPraktikum = apps.get_model('jadwal', 'JadwalPraktikum')
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')
    fallback_ruangan = None

    for jadwal in JadwalPraktikum.objects.all():
        if not fallback_ruangan:
            fallback_ruangan = RuanganLab.objects.order_by('nama').first()

        ruangan = (
            RuanganLab.objects.filter(nama__iexact=jadwal.letak_ruangan.strip()).first()
            or RuanganLab.objects.filter(kode__iexact=jadwal.letak_ruangan.strip()).first()
            or fallback_ruangan
        )

        if not ruangan:
            ruangan = RuanganLab.objects.create(
                nama=jadwal.letak_ruangan or 'Ruangan Praktikum',
                kode='LAB-JADWAL',
                deskripsi='Dibuat otomatis saat migrasi jadwal praktikum.',
                warna='teal',
            )
            fallback_ruangan = ruangan

        jadwal.hari = DAY_MAP.get(jadwal.tanggal.weekday(), 'senin')
        jadwal.ruangan_baru = ruangan
        jadwal.save(update_fields=['hari', 'ruangan_baru'])


class Migration(migrations.Migration):

    dependencies = [
        ('ruangan', '0001_initial'),
        ('jadwal', '0002_rename_matkul_letak_ruangan'),
    ]

    operations = [
        migrations.AddField(
            model_name='jadwalpraktikum',
            name='hari',
            field=models.CharField(choices=[('senin', 'Senin'), ('selasa', 'Selasa'), ('rabu', 'Rabu'), ('kamis', 'Kamis'), ('jumat', 'Jumat'), ('sabtu', 'Sabtu')], default='senin', max_length=10),
        ),
        migrations.AddField(
            model_name='jadwalpraktikum',
            name='ruangan_baru',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='jadwal_praktikum', to='ruangan.ruanganlab'),
        ),
        migrations.RunPython(migrate_jadwal_to_hari_ruangan, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='jadwalpraktikum',
            name='tanggal',
        ),
        migrations.RemoveField(
            model_name='jadwalpraktikum',
            name='letak_ruangan',
        ),
        migrations.RenameField(
            model_name='jadwalpraktikum',
            old_name='ruangan_baru',
            new_name='ruangan',
        ),
        migrations.AlterField(
            model_name='jadwalpraktikum',
            name='ruangan',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='jadwal_praktikum', to='ruangan.ruanganlab'),
        ),
        migrations.AlterModelOptions(
            name='jadwalpraktikum',
            options={
                'ordering': ['hari', 'waktu_mulai', 'mata_kuliah'],
                'verbose_name': 'Jadwal Praktikum',
                'verbose_name_plural': 'Jadwal Praktikum',
            },
        ),
    ]
