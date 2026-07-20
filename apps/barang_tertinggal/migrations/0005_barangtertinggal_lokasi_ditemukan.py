from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('barang_tertinggal', '0004_barangtertinggal_nim_pemilik_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='barangtertinggal',
            name='lokasi_ditemukan',
            field=models.CharField(blank=True, max_length=180),
        ),
    ]
