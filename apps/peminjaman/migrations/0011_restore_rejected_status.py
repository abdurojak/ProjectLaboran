from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peminjaman', '0010_alter_peminjamanalat_status'),
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
