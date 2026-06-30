from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ruangan', '0001_initial'),
        ('jadwal', '0004_jadwal_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='jadwalpraktikum',
            name='ruangan_tambahan',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='jadwal_praktikum_tambahan',
                to='ruangan.ruanganlab',
            ),
        ),
    ]
