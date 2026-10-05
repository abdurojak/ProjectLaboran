from django.db import migrations


ALLOWED_PRODI = ('Informatika', 'Sistem Informasi')


def normalize_prodi(apps, schema_editor):
    Prodi = apps.get_model('pengguna', 'Prodi')
    Pengguna = apps.get_model('pengguna', 'Pengguna')

    for name in ALLOWED_PRODI:
        Prodi.objects.update_or_create(nama=name, defaults={'aktif': True})
    Prodi.objects.exclude(nama__in=ALLOWED_PRODI).delete()

    Pengguna.objects.filter(nim_nik__startswith='064').update(prodi='Informatika')
    Pengguna.objects.filter(nim_nik__startswith='065').update(prodi='Sistem Informasi')


class Migration(migrations.Migration):
    dependencies = [
        ('pengguna', '0018_pengguna_must_change_password'),
    ]

    operations = [
        migrations.RunPython(normalize_prodi, migrations.RunPython.noop),
    ]
