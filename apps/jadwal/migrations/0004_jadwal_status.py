from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jadwal', '0003_jadwal_hari_ruangan'),
    ]

    operations = [
        migrations.AddField(
            model_name='jadwalpraktikum',
            name='status',
            field=models.CharField(
                choices=[
                    ('diajukan', 'Diajukan'),
                    ('diterima', 'Diterima'),
                    ('ditolak', 'Ditolak'),
                ],
                default='diterima',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='jadwalpraktikum',
            name='status',
            field=models.CharField(
                choices=[
                    ('diajukan', 'Diajukan'),
                    ('diterima', 'Diterima'),
                    ('ditolak', 'Ditolak'),
                ],
                default='diajukan',
                max_length=20,
            ),
        ),
    ]
