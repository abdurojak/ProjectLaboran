from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('jadwal', '0006_permintaanperubahanjadwal'),
        ('asleb', '0022_modulpraktikum_file_size_modulpraktikum_file_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='absensiasleb',
            name='jadwal',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='absensi_asleb',
                to='jadwal.jadwalpraktikum',
            ),
        ),
        migrations.AlterField(
            model_name='absensimasukasleb',
            name='jadwal',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='absensi_masuk_asleb',
                to='jadwal.jadwalpraktikum',
            ),
        ),
    ]
