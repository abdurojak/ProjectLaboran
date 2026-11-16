from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('asleb', '0035_task_management')]

    operations = [
        migrations.AddField(
            model_name='hasilpraktikummahasiswa',
            name='sumber_absensi',
            field=models.CharField(
                choices=[('manual', 'Manual'), ('qr', 'QR mahasiswa')],
                default='manual', max_length=10,
            ),
        ),
    ]
