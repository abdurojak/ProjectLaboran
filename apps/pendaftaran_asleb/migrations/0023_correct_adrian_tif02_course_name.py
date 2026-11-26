from django.db import migrations


OLD_NAME = 'Keamanan Komputasi'
NEW_NAME = 'Keamanan Informasi'
COURSE_CODE = 'KI_TIF02_ADRIAN'
CLASS = 'TIF-02'


def correct_adrian_course(apps, schema_editor):
    course_model = apps.get_model('pendaftaran_asleb', 'MataKuliahAsleb')
    asleb_model = apps.get_model('asleb', 'Asleb')
    schedule_model = apps.get_model('jadwal', 'JadwalPraktikum')

    course = course_model.objects.filter(
        kode=COURSE_CODE,
        kelas=CLASS,
        dosen__icontains='Adrian',
        nama=OLD_NAME,
    ).first()
    if course is None:
        return

    old_label = str(course)
    course.nama = NEW_NAME
    course.save(update_fields=['nama'])
    new_label = str(course)
    asleb_model.objects.filter(matkul=old_label).update(matkul=new_label)
    schedule_model.objects.filter(mata_kuliah=old_label, kelas=CLASS).update(
        mata_kuliah=new_label,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('pendaftaran_asleb', '0022_matakuliahasleb_laboratorium'),
        ('asleb', '0042_itembatchhonor_rincian_jam'),
        ('jadwal', '0006_permintaanperubahanjadwal'),
    ]

    operations = [
        migrations.RunPython(correct_adrian_course, migrations.RunPython.noop),
    ]
