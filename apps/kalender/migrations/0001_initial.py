from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='KegiatanKalender',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('judul', models.CharField(max_length=200)),
                ('tanggal', models.DateField()),
                ('waktu_mulai', models.TimeField()),
                ('waktu_selesai', models.TimeField(blank=True, null=True)),
                ('lokasi', models.CharField(blank=True, max_length=150)),
                ('deskripsi', models.TextField(blank=True)),
                ('tampilkan_notifikasi', models.BooleanField(default=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['tanggal', 'waktu_mulai', 'judul'],
                'verbose_name': 'Kegiatan Kalender',
                'verbose_name_plural': 'Kegiatan Kalender',
            },
        ),
    ]

