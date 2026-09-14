import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pendaftaran_asleb', '0018_aslab_replacement_workflow'),
        ('pengguna', '0016_rename_pengguna_sc_npsn_36628f_idx_pengguna_sc_npsn_495644_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='KoreksiPengalamanAsleb',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nim', models.CharField(max_length=30, unique=True, verbose_name='NIM')),
                ('jumlah_periode', models.PositiveSmallIntegerField(validators=[django.core.validators.MaxValueValidator(99)], verbose_name='Jumlah periode Aslab')),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('diatur_oleh', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='koreksi_pengalaman_asleb', to='pengguna.pengguna')),
            ],
            options={
                'verbose_name': 'Koreksi Pengalaman Aslab',
                'verbose_name_plural': 'Koreksi Pengalaman Aslab',
                'ordering': ['nim'],
            },
        ),
    ]
