from .models import AslabAssignment, PendaftaranAsleb, RiwayatAsleb


REGISTRATION_LIMIT = 3
OVERRIDE_PHRASE = 'TERIMA DI LUAR BATAS'


def academic_semester_from_nim(nim, period):
    nim = str(nim or '').strip()
    if len(nim) < 10 or not nim.isdigit():
        return None
    cohort = 2000 + int(nim[5:7])
    semester = 2 * (period.tahun - cohort) + (1 if period.semester == 2 else 0)
    return semester if semester > 0 else None


def acceptance_limit(nim, period):
    semester = academic_semester_from_nim(nim, period)
    return 2 if semester is not None and semester >= 5 else 1


def accepted_course_ids(nim, period):
    course_ids = set(PendaftaranAsleb.objects.filter(
        nim=nim, periode=period, status__in=['diterima', 'digenerate'],
    ).values_list('matkul_id', flat=True))
    course_ids.update(RiwayatAsleb.objects.filter(
        nim=nim, periode=period,
    ).values_list('matkul_id', flat=True))
    course_ids.update(AslabAssignment.objects.filter(
        asleb__nim=nim, slot__periode=period,
    ).exclude(status=AslabAssignment.STATUS_CANCELLED).values_list('slot__matkul_id', flat=True))
    return course_ids
