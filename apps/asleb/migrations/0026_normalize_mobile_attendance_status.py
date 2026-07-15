from django.db import migrations, models


def normalize_mobile_attendance_status(apps, schema_editor):
    AbsensiMasukAsleb = apps.get_model('asleb', 'AbsensiMasukAsleb')
    AbsensiMasukAsleb.objects.filter(status='terlambat').update(status='sudah_absen')


class Migration(migrations.Migration):

    dependencies = [
        ('asleb', '0025_remove_absensi_unique_nomor_modul'),
    ]

    operations = [
        migrations.RunPython(normalize_mobile_attendance_status, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='absensimasukasleb',
            name='status',
            field=models.CharField(choices=[('sudah_absen', 'Sudah Absen')], default='sudah_absen', max_length=20),
        ),
    ]
