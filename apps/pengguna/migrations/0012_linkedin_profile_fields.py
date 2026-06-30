from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pengguna', '0011_pengalamanpengguna')]

    operations = [
        migrations.AddField(
            model_name='pengguna',
            name='ringkasan_profesional',
            field=models.TextField(blank=True, verbose_name='Tentang'),
        ),
        migrations.AddField(
            model_name='pengguna',
            name='keahlian',
            field=models.TextField(blank=True, help_text='Pisahkan setiap keahlian dengan koma.', verbose_name='Keahlian'),
        ),
        migrations.AddField(
            model_name='pengalamanpengguna',
            name='kategori',
            field=models.CharField(choices=[('pengalaman', 'Pengalaman'), ('pendidikan', 'Pendidikan'), ('organisasi', 'Organisasi'), ('proyek', 'Proyek'), ('sertifikasi', 'Lisensi & Sertifikasi')], default='pengalaman', max_length=20),
        ),
        migrations.AddField(model_name='pengalamanpengguna', name='bidang_studi', field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name='pengalamanpengguna', name='lokasi', field=models.CharField(blank=True, max_length=150)),
    ]
