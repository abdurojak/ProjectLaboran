from django.db import migrations


LABORAN_BY_ROOM_CODE = {
    'LAB-PRG': 'Muhamad Ichsan Gunawan, S.Kom.',
    'LAB-SDA': 'Muhammad Fikri, S.Kom.',
    'LAB-SKI': 'Ricardo Dharma Saputra, S.Kom.',
    'LAB-RPL': 'Abdurojak, S.Tr.Kom.',
    'LAB-RD': 'Faiz Kumara, S.Kom.',
}


PREVIOUS_HEAD_BY_ROOM_CODE = {
    'LAB-PRG': 'Anung B. Ariwibowo, M. Kom',
    'LAB-SDA': 'Dian Pratiwi, ST, MTI',
    'LAB-SKI': 'Ir. Gatot Budi Santoso, M.Kom.',
    'LAB-RPL': 'Drs. Syaifudin, M.Si., Ph.D.',
    'LAB-RD': 'Is Mardianto, S. Si, M. Kom',
}


def update_laboran(apps, schema_editor):
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')
    for kode, laboran in LABORAN_BY_ROOM_CODE.items():
        RuanganLab.objects.filter(kode=kode).update(kepala_lab=laboran)


def restore_previous_heads(apps, schema_editor):
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')
    for kode, kepala_lab in PREVIOUS_HEAD_BY_ROOM_CODE.items():
        RuanganLab.objects.filter(kode=kode).update(kepala_lab=kepala_lab)


class Migration(migrations.Migration):

    dependencies = [
        ('ruangan', '0005_ruanganlab_kepala_lab_update_defaults'),
    ]

    operations = [
        migrations.RunPython(update_laboran, restore_previous_heads),
    ]
