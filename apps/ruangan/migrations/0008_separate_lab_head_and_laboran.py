from django.db import migrations, models


LAB_ASSIGNMENTS = {
    'LAB-PRG': {
        'kepala_lab': 'Anung B. Ariwibowo, M. Kom',
        'laboran': 'Muhamad Ichsan Gunawan, S.Kom.',
    },
    'LAB-SDA': {
        'kepala_lab': 'Dian Pratiwi, ST, MTI',
        'laboran': 'Muhammad Fikri, S.Kom.',
    },
    'LAB-SKI': {
        'kepala_lab': 'Ir. Gatot Budi Santoso, M.Kom.',
        'laboran': 'Ricardo Dharma Saputra, S.Kom.',
    },
    'LAB-RPL': {
        'kepala_lab': 'Drs. Syaifudin, M.Si., Ph.D.',
        'laboran': 'Abdurojak, S.Tr.Kom.',
    },
    'LAB-RD': {
        'kepala_lab': 'Is Mardianto, S. Si, M. Kom',
        'laboran': 'Faiz Kumara, S.Kom.',
    },
}


def separate_assignments(apps, schema_editor):
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')
    for kode, assignment in LAB_ASSIGNMENTS.items():
        RuanganLab.objects.filter(kode=kode).update(**assignment)
    RuanganLab.objects.filter(kode='KELAS-PARALEL').update(tampil_di_daftar_lab=False)


def restore_previous_data(apps, schema_editor):
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')
    for kode, assignment in LAB_ASSIGNMENTS.items():
        RuanganLab.objects.filter(kode=kode).update(
            kepala_lab=assignment['laboran'],
            laboran='',
        )
    RuanganLab.objects.filter(kode='KELAS-PARALEL').update(tampil_di_daftar_lab=True)


class Migration(migrations.Migration):

    dependencies = [
        ('ruangan', '0007_ruanganlab_unlimited_capacity'),
    ]

    operations = [
        migrations.AddField(
            model_name='ruanganlab',
            name='laboran',
            field=models.CharField(blank=True, max_length=150, verbose_name='Laboran'),
        ),
        migrations.AddField(
            model_name='ruanganlab',
            name='tampil_di_daftar_lab',
            field=models.BooleanField(default=True, verbose_name='Tampil di Daftar Lab'),
        ),
        migrations.RunPython(separate_assignments, restore_previous_data),
    ]
