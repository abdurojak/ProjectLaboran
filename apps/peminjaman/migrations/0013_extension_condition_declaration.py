from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peminjaman', '0012_peminjaman_credit_extension'),
    ]

    operations = [
        migrations.AddField(
            model_name='pengajuanperpanjangan',
            name='keterangan_kondisi',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='pengajuanperpanjangan',
            name='kondisi_barang',
            field=models.CharField(
                choices=[('baik', 'Masih baik'), ('tidak_baik', 'Tidak baik / ada masalah')],
                default='baik',
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name='pengajuanperpanjangan',
            name='pernyataan_jujur',
            field=models.BooleanField(default=False),
        ),
    ]
