from django.db import migrations, models


PARALLEL_CLASS_CODE = 'KELAS-PARALEL'


def seed_parallel_class(apps, schema_editor):
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')
    RuanganLab.objects.update_or_create(
        kode=PARALLEL_CLASS_CODE,
        defaults={
            'nama': 'Kelas Paralel',
            'kepala_lab': '',
            'deskripsi': 'Pilihan kelas paralel untuk jumlah peserta tanpa batas kapasitas ruangan.',
            'kapasitas': None,
            'kapasitas_tak_terbatas': True,
            'warna': 'teal',
            'aktif': True,
        },
    )


def remove_parallel_class(apps, schema_editor):
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')
    RuanganLab.objects.filter(kode=PARALLEL_CLASS_CODE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ruangan', '0006_update_laboran_ruangan'),
    ]

    operations = [
        migrations.AddField(
            model_name='ruanganlab',
            name='kapasitas_tak_terbatas',
            field=models.BooleanField(default=False, verbose_name='Kapasitas Tak Terbatas'),
        ),
        migrations.RunPython(seed_parallel_class, remove_parallel_class),
    ]
