from django.db import migrations


ACCEPTED_STATUSES = ('diterima', 'digenerate')


def course_label(course):
    return f'{course.nama} - {course.dosen} - {course.kelas}'


def matching_registration(PendaftaranAsleb, asleb):
    candidates = list(
        PendaftaranAsleb.objects.filter(
            nim=asleb.nim,
            periode_id=asleb.periode_aktif_id,
            status__in=ACCEPTED_STATUSES,
        ).select_related('matkul').order_by('pk')
    )
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1 and asleb.matkul:
        exact = [item for item in candidates if course_label(item.matkul) == asleb.matkul]
        if len(exact) == 1:
            return exact[0]
    return None


def backfill_aslab_assignments(apps, schema_editor):
    Asleb = apps.get_model('asleb', 'Asleb')
    PendaftaranAsleb = apps.get_model('pendaftaran_asleb', 'PendaftaranAsleb')
    AslabSlot = apps.get_model('pendaftaran_asleb', 'AslabSlot')
    AslabAssignment = apps.get_model('pendaftaran_asleb', 'AslabAssignment')

    active_aslebs = Asleb.objects.filter(
        status='aktif',
        periode_aktif__isnull=False,
    ).select_related('periode_aktif').order_by('pk')

    for asleb in active_aslebs.iterator():
        if AslabAssignment.objects.filter(asleb_id=asleb.pk, status='active').exists():
            continue

        registration = matching_registration(PendaftaranAsleb, asleb)
        if registration is None:
            continue

        occupied = set(
            AslabAssignment.objects.filter(
                slot__periode_id=asleb.periode_aktif_id,
                slot__matkul_id=registration.matkul_id,
                status='active',
            ).values_list('slot__nomor', flat=True)
        )
        unavailable = occupied | set(
            AslabSlot.objects.filter(
                periode_id=asleb.periode_aktif_id,
                matkul_id=registration.matkul_id,
                status='closed',
            ).values_list('nomor', flat=True)
        )
        free_number = next((number for number in (1, 2) if number not in unavailable), None)
        if free_number is None:
            continue

        slot, _ = AslabSlot.objects.get_or_create(
            periode_id=asleb.periode_aktif_id,
            matkul_id=registration.matkul_id,
            nomor=free_number,
            defaults={'status': 'active'},
        )
        if slot.status != 'active':
            slot.status = 'active'
            slot.save(update_fields=['status', 'diperbarui_pada'])
        AslabAssignment.objects.create(
            slot_id=slot.pk,
            active_slot_id=slot.pk,
            asleb_id=asleb.pk,
            source_pendaftaran_id=registration.pk,
            mulai_pada=asleb.periode_aktif.mulai,
            status='active',
        )


class Migration(migrations.Migration):
    dependencies = [
        ('pendaftaran_asleb', '0016_aslab_assignment_foundation'),
    ]

    operations = [
        migrations.RunPython(
            backfill_aslab_assignments,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
