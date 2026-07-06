from django.db import migrations, models


def seed_default_combined_room_group(apps, schema_editor):
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')
    GrupRuanganGabungan = apps.get_model('ruangan', 'GrupRuanganGabungan')

    rooms = list(RuanganLab.objects.filter(kode__in=['LAB-RPL', 'LAB-SKI']))
    if len(rooms) != 2:
        return

    group, _ = GrupRuanganGabungan.objects.update_or_create(
        nama='Lab RPL dan Lab SKI',
        defaults={
            'deskripsi': 'Dua lab berdampingan yang dapat digunakan sebagai satu ruang praktikum gabungan.',
            'aktif': True,
        },
    )
    group.ruangan.set(rooms)


def remove_default_combined_room_group(apps, schema_editor):
    GrupRuanganGabungan = apps.get_model('ruangan', 'GrupRuanganGabungan')
    GrupRuanganGabungan.objects.filter(nama='Lab RPL dan Lab SKI').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ruangan', '0002_update_lab_capacities'),
    ]

    operations = [
        migrations.CreateModel(
            name='GrupRuanganGabungan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nama', models.CharField(max_length=150)),
                ('deskripsi', models.TextField(blank=True)),
                ('aktif', models.BooleanField(default=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('ruangan', models.ManyToManyField(related_name='grup_gabungan', to='ruangan.ruanganlab')),
            ],
            options={
                'verbose_name': 'Grup Ruangan Gabungan',
                'verbose_name_plural': 'Grup Ruangan Gabungan',
                'ordering': ['nama'],
            },
        ),
        migrations.RunPython(seed_default_combined_room_group, remove_default_combined_room_group),
    ]
