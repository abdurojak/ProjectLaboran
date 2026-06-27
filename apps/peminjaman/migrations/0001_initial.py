from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('inventaris', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PeminjamanAlat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nama_peminjam', models.CharField(max_length=150)),
                ('kelas_tujuan', models.CharField(blank=True, max_length=100)),
                ('jumlah', models.PositiveIntegerField(default=1)),
                ('tanggal_pinjam', models.DateField()),
                ('tanggal_kembali', models.DateField()),
                ('status', models.CharField(choices=[('diajukan', 'Diajukan'), ('dipinjam', 'Dipinjam'), ('dikembalikan', 'Dikembalikan')], default='diajukan', max_length=20)),
                ('catatan', models.TextField(blank=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('barang', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='peminjaman', to='inventaris.barang')),
            ],
            options={
                'ordering': ['-tanggal_pinjam', '-dibuat_pada'],
                'verbose_name': 'Peminjaman Alat',
                'verbose_name_plural': 'Peminjaman Alat',
            },
        ),
    ]

