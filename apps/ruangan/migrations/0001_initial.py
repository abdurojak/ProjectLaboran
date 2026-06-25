from django.db import migrations, models


DEFAULT_RUANGAN = [
    {
        'nama': 'Lab Rekayasa Perangkat Lunak',
        'kode': 'LAB-RPL',
        'deskripsi': 'Ruang praktik untuk pengembangan aplikasi, pemrograman, dan proyek perangkat lunak.',
        'kapasitas': 20,
        'warna': 'teal',
    },
    {
        'nama': 'Lab Sistem Keamanan Informasi',
        'kode': 'LAB-SKI',
        'deskripsi': 'Ruang praktik untuk simulasi keamanan jaringan, hardening sistem, dan pengujian keamanan.',
        'kapasitas': 18,
        'warna': 'amber',
    },
    {
        'nama': 'Lab Pemrograman',
        'kode': 'LAB-PRG',
        'deskripsi': 'Ruang utama untuk praktikum algoritma, coding dasar, dan eksperimen aplikasi.',
        'kapasitas': 39,
        'warna': 'blue',
    },
    {
        'nama': 'Lab SDA',
        'kode': 'LAB-SDA',
        'deskripsi': 'Ruang untuk praktikum yang berfokus pada sistem digital, analisis data, dan eksperimen komputasi.',
        'kapasitas': 13,
        'warna': 'emerald',
    },
    {
        'nama': 'Lab Rekayasa Data',
        'kode': 'LAB-RD',
        'deskripsi': 'Ruang praktik untuk basis data, pipeline data, dan pemodelan data terapan.',
        'kapasitas': None,
        'warna': 'violet',
    },
]


def seed_default_ruangan(apps, schema_editor):
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')

    for data in DEFAULT_RUANGAN:
        RuanganLab.objects.update_or_create(
            kode=data['kode'],
            defaults=data,
        )


def remove_default_ruangan(apps, schema_editor):
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')
    RuanganLab.objects.filter(kode__in=[data['kode'] for data in DEFAULT_RUANGAN]).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='RuanganLab',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nama', models.CharField(max_length=150)),
                ('kode', models.CharField(max_length=30, unique=True)),
                ('deskripsi', models.TextField(blank=True)),
                ('kapasitas', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('warna', models.CharField(choices=[('teal', 'Teal'), ('amber', 'Amber'), ('blue', 'Biru'), ('emerald', 'Emerald'), ('violet', 'Violet')], default='teal', max_length=20)),
                ('aktif', models.BooleanField(default=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Ruangan Lab',
                'verbose_name_plural': 'Ruangan Lab',
                'ordering': ['nama'],
            },
        ),
        migrations.RunPython(seed_default_ruangan, remove_default_ruangan),
    ]
