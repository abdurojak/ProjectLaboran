from django.db import migrations


FAKULTAS = [
    'Teknologi Industri',
    'Ekonomi',
    'Teknologi Kebumian dan Energi',
    'Arsitektur Lanskap dan Teknologi Lingkungan',
    'Teknik Sipil dan Perencanaan',
    'Kedokteran Gigi',
    'Kedokteran',
    'Hukum',
    'Seni Rupa dan Desain',
]

PRODI = [
    'Informatika',
    'Sistem Informasi',
    'Rekayasa Perangkat Lunak',
    'Sistem Keamanan Informasi',
    'Rekayasa Data',
    'Manajemen',
    'Akuntansi',
    'Teknik Industri',
    'Teknik Elektro',
    'Teknik Mesin',
    'Teknik Sipil',
]


def seed_master_data(apps, schema_editor):
    Fakultas = apps.get_model('pengguna', 'Fakultas')
    Prodi = apps.get_model('pengguna', 'Prodi')

    for nama in FAKULTAS:
        Fakultas.objects.get_or_create(nama=nama, defaults={'aktif': True})

    for nama in PRODI:
        Prodi.objects.get_or_create(nama=nama, defaults={'aktif': True})


def remove_master_data(apps, schema_editor):
    Fakultas = apps.get_model('pengguna', 'Fakultas')
    Prodi = apps.get_model('pengguna', 'Prodi')

    Fakultas.objects.filter(nama__in=FAKULTAS).delete()
    Prodi.objects.filter(nama__in=PRODI).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pengguna', '0005_fakultas_prodi'),
    ]

    operations = [
        migrations.RunPython(seed_master_data, remove_master_data),
    ]
