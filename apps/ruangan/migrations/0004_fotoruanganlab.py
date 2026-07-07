from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ruangan', '0003_grupruangangabungan'),
    ]

    operations = [
        migrations.CreateModel(
            name='FotoRuanganLab',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gambar', models.ImageField(upload_to='ruangan_lab/')),
                ('judul', models.CharField(blank=True, max_length=120)),
                ('urutan', models.PositiveSmallIntegerField(default=0)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('ruangan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='foto_lab', to='ruangan.ruanganlab')),
            ],
            options={
                'verbose_name': 'Foto Ruangan Lab',
                'verbose_name_plural': 'Foto Ruangan Lab',
                'ordering': ['urutan', '-dibuat_pada'],
            },
        ),
    ]

