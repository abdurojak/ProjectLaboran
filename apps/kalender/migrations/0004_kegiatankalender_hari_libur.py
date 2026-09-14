from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kalender', '0003_notifikasi_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='kegiatankalender',
            name='hari_libur',
            field=models.BooleanField(
                default=False,
                help_text='Tandai jika laboratorium tutup dan pengembalian barang perlu diundur.',
            ),
        ),
    ]
