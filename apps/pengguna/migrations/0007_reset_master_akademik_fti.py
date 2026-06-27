from django.db import migrations


ACTIVE_FAKULTAS = ['Teknologi Industri']

ACTIVE_PRODI = [
    'Mesin',
    'Elektro',
    'Industri',
    'Informatika',
    'Sistem Informasi',
]


def reset_master_akademik(apps, schema_editor):
    Fakultas = apps.get_model('pengguna', 'Fakultas')
    Prodi = apps.get_model('pengguna', 'Prodi')

    Fakultas.objects.exclude(nama__in=ACTIVE_FAKULTAS).update(aktif=False)
    Prodi.objects.exclude(nama__in=ACTIVE_PRODI).update(aktif=False)

    for nama in ACTIVE_FAKULTAS:
        Fakultas.objects.update_or_create(nama=nama, defaults={'aktif': True})

    for nama in ACTIVE_PRODI:
        Prodi.objects.update_or_create(nama=nama, defaults={'aktif': True})


def restore_previous_master_akademik(apps, schema_editor):
    Fakultas = apps.get_model('pengguna', 'Fakultas')
    Prodi = apps.get_model('pengguna', 'Prodi')

    Fakultas.objects.all().update(aktif=True)
    Prodi.objects.all().update(aktif=True)


class Migration(migrations.Migration):

    dependencies = [
        ('pengguna', '0006_seed_fakultas_prodi'),
    ]

    operations = [
        migrations.RunPython(reset_master_akademik, restore_previous_master_akademik),
    ]
