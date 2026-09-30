from datetime import datetime, time, timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.asleb.models import AbsensiAsleb, AbsensiMasukAsleb, Asleb, ModulPraktikum
from apps.asleb.services import (
    get_active_asleb_for_pengguna,
    get_active_asleb_matkul_ids,
    get_active_asleb_period,
    get_asleb_matkul_for_schedule,
)
from apps.jadwal.models import JadwalPraktikum
from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb, RiwayatAsleb


WEEKDAY_KEYS = ['senin', 'selasa', 'rabu', 'kamis', 'jumat', 'sabtu', 'minggu']


def get_active_asleb(pengguna):
    return get_active_asleb_for_pengguna(pengguna)


def get_asleb_courses(asleb):
    assigned_ids = get_active_asleb_matkul_ids(asleb)
    if assigned_ids:
        # Penugasan aktif adalah sumber utama. Flag aktif pada master mata kuliah
        # dapat tertinggal saat data semester diperbarui, sehingga tidak boleh
        # menghilangkan jadwal yang masih resmi ditugaskan kepada Aslab.
        return list(
            MataKuliahAsleb.objects.filter(pk__in=assigned_ids)
            .order_by('nama', 'kelas', 'pk')
        )
    return []


def get_asleb_course_labels(asleb):
    assigned_courses = get_asleb_courses(asleb)
    if assigned_courses:
        return [str(course) for course in assigned_courses]

    registrations = PendaftaranAsleb.objects.filter(
        nim=asleb.nim,
        status__in=['diterima', 'digenerate'],
    )
    history = RiwayatAsleb.objects.filter(nim=asleb.nim)
    if asleb.periode_aktif_id:
        registrations = registrations.filter(periode_id=asleb.periode_aktif_id)
        history = history.filter(periode_id=asleb.periode_aktif_id)
    else:
        registrations = registrations.filter(periode__isnull=True)
        history = history.none()
    registrations = registrations.select_related('matkul')
    history = history.select_related('matkul')
    labels = {str(item.matkul) for item in registrations}
    labels.update(str(item.matkul) for item in history)
    if asleb.matkul:
        labels.add(asleb.matkul)
    return sorted(labels)


def get_owned_schedules(asleb):
    courses = get_asleb_courses(asleb)
    if not courses:
        labels = get_asleb_course_labels(asleb)
        if not labels:
            return JadwalPraktikum.objects.none()
        return JadwalPraktikum.objects.filter(
            mata_kuliah__in=labels,
            status=JadwalPraktikum.STATUS_DITERIMA,
        ).select_related('ruangan', 'ruangan_tambahan')

    schedule_match = Q()
    for course in courses:
        schedule_match |= Q(mata_kuliah=str(course))
        if course.nama and course.kelas:
            schedule_match |= Q(
                mata_kuliah__istartswith=f'{course.nama} - ',
                kelas__iexact=course.kelas.strip(),
            )
    if not schedule_match:
        return JadwalPraktikum.objects.none()
    return JadwalPraktikum.objects.filter(
        schedule_match,
        status=JadwalPraktikum.STATUS_DITERIMA,
    ).select_related('ruangan', 'ruangan_tambahan').distinct()


def get_available_modules(asleb, schedule):
    period = get_active_asleb_period(asleb)
    course = get_asleb_matkul_for_schedule(asleb, schedule)
    if period is None or course is None:
        return ModulPraktikum.objects.none()

    used_ids = set(
        AbsensiAsleb.objects.filter(
            asleb=asleb,
            periode=period,
            modul_praktikum__isnull=False,
        ).values_list('modul_praktikum_id', flat=True)
    )
    used_ids.update(
        AbsensiMasukAsleb.objects.filter(
            asleb=asleb,
            periode=period,
            modul_praktikum__isnull=False,
        ).values_list('modul_praktikum_id', flat=True)
    )
    return ModulPraktikum.objects.filter(matkul=course).exclude(pk__in=used_ids).order_by('nomor', 'pk')


def aware_schedule_datetime(date_value, time_value):
    value = datetime.combine(date_value, time_value)
    return timezone.make_aware(value, timezone.get_current_timezone())


def get_checkin_window(schedule, date_value):
    opens_at = aware_schedule_datetime(date_value, time.min)
    starts_at = aware_schedule_datetime(date_value, schedule.waktu_mulai)
    closes_at = opens_at + timedelta(days=1)
    return opens_at, starts_at, closes_at


def validate_schedule_time(schedule, now=None):
    now = now or timezone.now()
    local_now = timezone.localtime(now)
    today = local_now.date()
    if schedule.hari != WEEKDAY_KEYS[today.weekday()]:
        return False, 'Jadwal praktikum bukan untuk hari ini.', None
    opens_at, _, closes_at = get_checkin_window(schedule, today)
    if local_now < opens_at:
        return False, 'Absensi untuk jadwal hari ini belum dibuka.', None
    if local_now >= closes_at:
        return False, 'Batas absensi hari ini sudah berakhir.', None
    status = AbsensiMasukAsleb.STATUS_SUDAH_ABSEN
    return True, '', status


def calculate_distance_meters(latitude, longitude):
    latitude = float(latitude)
    longitude = float(longitude)
    target_latitude = settings.ABSENSI_CENTER_LATITUDE
    target_longitude = settings.ABSENSI_CENTER_LONGITUDE
    earth_radius = 6371000
    lat1, lat2 = radians(latitude), radians(target_latitude)
    delta_lat = radians(target_latitude - latitude)
    delta_lon = radians(target_longitude - longitude)
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return Decimal(str(earth_radius * 2 * asin(sqrt(value)))).quantize(Decimal('0.01'))


def get_schedule_attendance(schedule, asleb, date_value=None):
    date_value = date_value or timezone.localdate()
    return AbsensiMasukAsleb.objects.filter(
        asleb=asleb,
        jadwal=schedule,
        tanggal_absensi=date_value,
    ).first()
