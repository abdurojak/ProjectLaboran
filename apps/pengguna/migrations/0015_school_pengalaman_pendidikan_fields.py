from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pengguna', '0014_pengalamanpengguna_file_sertifikat_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='School',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('npsn', models.CharField(max_length=20, unique=True)),
                ('nama', models.CharField(db_index=True, max_length=180)),
                ('jenjang', models.CharField(choices=[('SD', 'SD'), ('SMP', 'SMP'), ('SMA', 'SMA'), ('SMK', 'SMK')], db_index=True, max_length=20)),
                ('status', models.CharField(choices=[('negeri', 'Negeri'), ('swasta', 'Swasta'), ('lainnya', 'Lainnya')], default='lainnya', max_length=20)),
                ('provinsi', models.CharField(blank=True, db_index=True, max_length=120)),
                ('kabupaten_kota', models.CharField(blank=True, db_index=True, max_length=120)),
                ('kecamatan', models.CharField(blank=True, max_length=120)),
                ('alamat', models.CharField(blank=True, max_length=260)),
                ('aktif', models.BooleanField(default=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Sekolah',
                'verbose_name_plural': 'Sekolah',
                'ordering': ['nama'],
            },
        ),
        migrations.AddField(
            model_name='pengalamanpengguna',
            name='jenjang_pendidikan',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='pengalamanpengguna',
            name='nama_sekolah_manual',
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name='pengalamanpengguna',
            name='nilai_akhir',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='pengalamanpengguna',
            name='sekolah_npsn',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='pengalamanpengguna',
            name='sekolah_snapshot',
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name='pengalamanpengguna',
            name='sekolah',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='riwayat_pendidikan', to='pengguna.school'),
        ),
        migrations.AddIndex(
            model_name='school',
            index=models.Index(fields=['npsn'], name='pengguna_sc_npsn_36628f_idx'),
        ),
        migrations.AddIndex(
            model_name='school',
            index=models.Index(fields=['jenjang', 'nama'], name='pengguna_sc_jenjang_c50f29_idx'),
        ),
        migrations.AddIndex(
            model_name='school',
            index=models.Index(fields=['provinsi', 'kabupaten_kota'], name='pengguna_sc_provins_1bbd39_idx'),
        ),
    ]
