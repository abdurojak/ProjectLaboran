from django.db import migrations, models


LAB_DEFAULTS = {
    'Lab Pemrograman': 'Anung B. Ariwibowo, M. Kom',
    'Lab Rekayasa Data': 'Is Mardianto, S. Si, M. Kom',
    'Lab Rekayasa Perangkat Lunak': 'Drs. Syaifudin, M.Si., Ph.D.',
    'Lab Sains Data dan Analitik': 'Dian Pratiwi, ST, MTI',
    'Lab Sistem Keamanan Informasi': 'Ir. Gatot Budi Santoso, M.Kom.',
}


def seed_lab_heads(apps, schema_editor):
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')
    RuanganLab.objects.filter(nama__iexact='Lab SDA').update(nama='Lab Sains Data dan Analitik', kapasitas=20)
    RuanganLab.objects.filter(nama__iexact='Lab Rekayasa Data').update(kapasitas=30)
    for nama, kepala_lab in LAB_DEFAULTS.items():
        RuanganLab.objects.filter(nama__iexact=nama).update(kepala_lab=kepala_lab)


class Migration(migrations.Migration):

    dependencies = [
        ('ruangan', '0004_fotoruanganlab'),
    ]

    operations = [
        migrations.AddField(
            model_name='ruanganlab',
            name='kepala_lab',
            field=models.CharField(blank=True, max_length=150, verbose_name='Kepala Lab'),
        ),
        migrations.RunPython(seed_lab_heads, migrations.RunPython.noop),
    ]
