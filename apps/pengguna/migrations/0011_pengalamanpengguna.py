from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [('pengguna', '0010_pengguna_cv')]

    operations = [
        migrations.CreateModel(
            name='PengalamanPengguna',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jabatan', models.CharField(max_length=150)),
                ('organisasi', models.CharField(max_length=150)),
                ('tanggal_mulai', models.DateField()),
                ('tanggal_selesai', models.DateField(blank=True, null=True)),
                ('masih_berjalan', models.BooleanField(default=False)),
                ('deskripsi', models.TextField(blank=True)),
                ('otomatis', models.BooleanField(default=False, editable=False)),
                ('source_key', models.CharField(blank=True, editable=False, max_length=100, null=True, unique=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('pengguna', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pengalaman', to='pengguna.pengguna')),
            ],
            options={'verbose_name': 'Pengalaman Pengguna', 'verbose_name_plural': 'Pengalaman Pengguna', 'ordering': ['-masih_berjalan', '-tanggal_mulai', '-pk']},
        ),
    ]
