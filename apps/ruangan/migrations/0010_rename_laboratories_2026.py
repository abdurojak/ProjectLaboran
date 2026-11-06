from django.db import migrations


LAB_NAMES = {
    'LAB-PRG': 'Laboratorium Pemrograman',
    'LAB-RPL': 'Laboratorium Rekayasa Perangkat Lunak',
    'LAB-SKI': 'Laboratorium Infrastruktur',
    'LAB-SDA': 'Laboratorium Bisnis Digital dan Analitik Data (Digital Business & Data Analytics Laboratory)',
    'LAB-RD': 'Laboratorium Sistem Cerdas',
}


def rename_laboratories(apps, schema_editor):
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')
    GrupRuanganGabungan = apps.get_model('ruangan', 'GrupRuanganGabungan')
    for code, name in LAB_NAMES.items():
        RuanganLab.objects.filter(kode=code).update(nama=name)
    GrupRuanganGabungan.objects.filter(nama='Lab RPL dan Lab SKI').update(
        nama='Laboratorium Rekayasa Perangkat Lunak dan Infrastruktur',
    )


class Migration(migrations.Migration):
    dependencies = [
        ('ruangan', '0009_ruanganlab_laboran_akun'),
    ]

    operations = [
        migrations.RunPython(rename_laboratories, migrations.RunPython.noop),
    ]
