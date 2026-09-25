import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('peminjaman', '0013_extension_condition_declaration'),
        ('pengguna', '0016_rename_pengguna_sc_npsn_36628f_idx_pengguna_sc_npsn_495644_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PenyesuaianSkorKredit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('skor_sebelum', models.PositiveSmallIntegerField()),
                ('skor_baru', models.PositiveSmallIntegerField()),
                ('nilai_penyesuaian', models.SmallIntegerField()),
                ('tautan_konten', models.URLField(blank=True)),
                ('catatan', models.CharField(max_length=300)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diubah_oleh', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='perubahan_skor_kredit_dibuat', to='pengguna.pengguna')),
                ('pengguna', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='penyesuaian_skor_kredit', to='pengguna.pengguna')),
            ],
            options={
                'verbose_name': 'Penyesuaian Skor Kredit',
                'verbose_name_plural': 'Penyesuaian Skor Kredit',
                'ordering': ['-dibuat_pada', '-pk'],
            },
        ),
    ]
