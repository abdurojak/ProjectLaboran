from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='JadwalPraktikum',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mata_praktikum', models.CharField(max_length=200)),
                ('kelas', models.CharField(max_length=100)),
                ('ruangan', models.CharField(max_length=150)),
                ('pengampu', models.CharField(max_length=150)),
                ('tanggal', models.DateField()),
                ('waktu_mulai', models.TimeField()),
                ('waktu_selesai', models.TimeField(blank=True, null=True)),
                ('catatan', models.TextField(blank=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['tanggal', 'waktu_mulai', 'mata_praktikum'],
                'verbose_name': 'Jadwal Praktikum',
                'verbose_name_plural': 'Jadwal Praktikum',
            },
        ),
    ]

