from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('pengguna', '0014_pengalamanpengguna_file_sertifikat_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='BugErrorLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('judul', models.CharField(max_length=180)),
                ('kategori', models.CharField(choices=[('bug', 'Bug'), ('error', 'Error'), ('ui', 'Tampilan/UI'), ('data', 'Data')], default='bug', max_length=20)),
                ('prioritas', models.CharField(choices=[('rendah', 'Rendah'), ('sedang', 'Sedang'), ('tinggi', 'Tinggi'), ('kritis', 'Kritis')], default='sedang', max_length=20)),
                ('lokasi', models.CharField(blank=True, max_length=500, verbose_name='Halaman/URL')),
                ('deskripsi', models.TextField()),
                ('langkah_reproduksi', models.TextField(blank=True)),
                ('ekspektasi', models.TextField(blank=True)),
                ('hasil_aktual', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('baru', 'Baru'), ('diproses', 'Diproses'), ('selesai', 'Selesai')], default='baru', max_length=20)),
                ('catatan_admin', models.TextField(blank=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('dilaporkan_oleh', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bug_error_logs', to='pengguna.pengguna')),
            ],
            options={
                'verbose_name': 'Bug & Error',
                'verbose_name_plural': 'Bug & Error List',
                'ordering': ['-dibuat_pada'],
            },
        ),
    ]
