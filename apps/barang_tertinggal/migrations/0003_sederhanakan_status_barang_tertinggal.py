from django.db import migrations, models


def normalisasi_status_barang_tertinggal(apps, schema_editor):
    BarangTertinggal = apps.get_model('barang_tertinggal', 'BarangTertinggal')
    BarangTertinggal.objects.filter(status__in=['diajukan', 'rusak']).update(status='tertinggal')


class Migration(migrations.Migration):

    dependencies = [
        ('barang_tertinggal', '0002_barangtertinggal_foto'),
    ]

    operations = [
        migrations.RunPython(normalisasi_status_barang_tertinggal, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='barangtertinggal',
            name='status',
            field=models.CharField(
                choices=[
                    ('tertinggal', 'Tertinggal'),
                    ('hilang', 'Hilang'),
                    ('diambil', 'Diambil'),
                ],
                default='tertinggal',
                max_length=20,
            ),
        ),
    ]
