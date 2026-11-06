from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('surat', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='suratpengadaan',
            name='hal',
            field=models.CharField(
                default='Permohonan Pengadaan Kebutuhan Fasilitas Laboratorium Infrastruktur',
                max_length=200,
            ),
        ),
        migrations.AlterField(
            model_name='suratpengadaan',
            name='laboratorium',
            field=models.CharField(default='Infrastruktur', max_length=150),
        ),
    ]
