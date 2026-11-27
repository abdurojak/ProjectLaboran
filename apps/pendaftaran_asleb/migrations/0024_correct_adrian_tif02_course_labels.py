from django.db import migrations


def correct_course_labels(apps, schema_editor):
    course_model = apps.get_model('pendaftaran_asleb', 'MataKuliahAsleb')
    asleb_model = apps.get_model('asleb', 'Asleb')
    schedule_model = apps.get_model('jadwal', 'JadwalPraktikum')

    course = course_model.objects.filter(
        kode='KI_TIF02_ADRIAN',
        kelas='TIF-02',
        dosen__icontains='Adrian',
        nama='Keamanan Informasi',
    ).first()
    if course is None:
        return

    old_label = f'Keamanan Komputasi - {course.dosen} - {course.kelas}'
    new_label = f'{course.nama} - {course.dosen} - {course.kelas}'
    asleb_model.objects.filter(matkul=old_label).update(matkul=new_label)
    schedule_model.objects.filter(mata_kuliah=old_label, kelas=course.kelas).update(
        mata_kuliah=new_label,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('pendaftaran_asleb', '0023_correct_adrian_tif02_course_name'),
    ]

    operations = [
        migrations.RunPython(correct_course_labels, migrations.RunPython.noop),
    ]
