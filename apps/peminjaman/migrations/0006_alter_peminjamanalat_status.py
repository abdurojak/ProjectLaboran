from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peminjaman', '0005_remove_peminjamanalat_jumlah'),
    ]

    operations = [
        migrations.AlterField(
            model_name='peminjamanalat',
            name='status',
            field=models.CharField(
                choices=[
                    ('diajukan', 'Diajukan'),
                    ('ditolak', 'Ditolak'),
                    ('dipinjam', 'Dipinjam'),
                    ('dikembalikan', 'Dikembalikan'),
                    ('hilang', 'Hilang'),
                    ('rusak', 'Rusak'),
                    ('digantikan', 'Digantikan'),
                ],
                default='diajukan',
                max_length=20,
            ),
        ),
    ]
