from django.db import migrations, models


def normalize_module_count(apps, schema_editor):
    HonorAsleb = apps.get_model('asleb', 'HonorAsleb')
    HonorAsleb.objects.filter(jumlah_praktikum=0).update(jumlah_praktikum=1)


class Migration(migrations.Migration):
    dependencies = [
        ('asleb', '0032_izin_absensi_manual_asleb'),
    ]

    operations = [
        migrations.RunPython(normalize_module_count, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='honorasleb',
            name='jumlah_praktikum',
            field=models.PositiveSmallIntegerField(default=1, verbose_name='Jumlah Modul'),
        ),
        migrations.AlterField(
            model_name='honorasleb',
            name='total_pertemuan',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Total Pertemuan'),
        ),
    ]
