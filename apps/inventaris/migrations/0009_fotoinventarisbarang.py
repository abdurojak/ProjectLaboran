from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventaris', '0008_paketbarang_paketbarangitem'),
    ]

    operations = [
        migrations.CreateModel(
            name='FotoInventarisBarang',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('foto', models.ImageField(upload_to='barang/galeri/')),
                ('urutan', models.PositiveSmallIntegerField(default=0)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('inventaris', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='galeri_foto', to='inventaris.inventarisbarang')),
            ],
            options={
                'verbose_name': 'Foto Galeri Inventaris',
                'verbose_name_plural': 'Foto Galeri Inventaris',
                'ordering': ['urutan', 'pk'],
            },
        ),
    ]
