from django.db import migrations, models


def move_draft_honors(apps, schema_editor):
    HonorAsleb = apps.get_model('asleb', 'HonorAsleb')
    HonorAsleb.objects.using(schema_editor.connection.alias).filter(status='draft').update(status='diproses')


class Migration(migrations.Migration):
    dependencies = [
        ('asleb', '0037_remove_absensimasukasleb_unique_absensi_masuk_asleb_jadwal_tanggal'),
    ]

    operations = [
        migrations.RunPython(move_draft_honors, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='honorasleb',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[('diproses', 'Diproses'), ('dibayar', 'Dibayar')],
                default='diproses',
            ),
        ),
    ]
