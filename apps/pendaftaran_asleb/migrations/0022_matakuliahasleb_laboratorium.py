from django.db import migrations, models
import django.db.models.deletion


LAB_PREFIXES = {
    'LAB-RPL': ('ERP_', 'PM_', 'PW_', 'MPTI_', 'PPB_'),
    'LAB-SDA': ('AD_', 'ADL_', 'ML_', 'NNDL_', 'KB_', 'BD_', 'PS_'),
    'LAB-RD': ('MDI_', 'MDIL_', 'DW_', 'PDDP_'),
    'LAB-PRG': ('AP_', 'PBO_', 'SDA_'),
    'LAB-SKI': ('JK_', 'KI_', 'AOK_', 'SO_'),
}


def assign_course_labs(apps, schema_editor):
    MataKuliahAsleb = apps.get_model('pendaftaran_asleb', 'MataKuliahAsleb')
    RuanganLab = apps.get_model('ruangan', 'RuanganLab')
    rooms = {room.kode: room for room in RuanganLab.objects.filter(kode__in=LAB_PREFIXES)}
    for course in MataKuliahAsleb.objects.all().iterator():
        for lab_code, prefixes in LAB_PREFIXES.items():
            if course.kode.upper().startswith(prefixes) and lab_code in rooms:
                course.laboratorium_id = rooms[lab_code].pk
                course.save(update_fields=['laboratorium'])
                break


class Migration(migrations.Migration):

    dependencies = [
        ('ruangan', '0008_separate_lab_head_and_laboran'),
        ('pendaftaran_asleb', '0021_keputusanseleksiasleb'),
    ]

    operations = [
        migrations.AddField(
            model_name='matakuliahasleb',
            name='laboratorium',
            field=models.ForeignKey(
                blank=True,
                help_text='Laboratorium pengelola mata kuliah untuk rekap dan surat honor Aslab.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mata_kuliah_aslab',
                to='ruangan.ruanganlab',
            ),
        ),
        migrations.RunPython(assign_course_labs, migrations.RunPython.noop),
    ]
