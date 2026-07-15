from datetime import datetime, timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from django.conf import settings
from django.utils import timezone

from apps.asleb.models import AbsensiMasukAsleb, Asleb
from apps.jadwal.models import JadwalPraktikum
from apps.pendaftaran_asleb.models import PendaftaranAsleb, RiwayatAsleb


WEEKDAY_KEYS = ['senin', 'selasa', 'rabu', 'kamis', 'jumat', 'sabtu', 'minggu']


def get_active_asleb(pengguna):
    return Asleb.objects.filter(nim=pengguna.nim_nik, status='aktif').select_related('periode_aktif').first()


def get_asleb_course_labels(asleb):
    registrations = PendaftaranAsleb.objects.filter(
        nim=asleb.nim,
        status__in=['diterima', 'digenerate'],
    ).select_related('matkul')
    history = RiwayatAsleb.objects.filter(nim=asleb.nim).select_related('matkul')
    labels = {str(item.matkul) for item in registrations}
    labels.update(str(item.matkul) for item in history)
    if asleb.matkul:
        labels.add(asleb.matkul)
    return sorted(labels)


def get_owned_schedules(asleb):
    labels = get_asleb_course_labels(asleb)
    if not labels:
        return JadwalPraktikum.objects.none()
    return JadwalPraktikum.objects.filter(
        mata_kuliah__in=labels,
        status=JadwalPraktikum.STATUS_DITERIMA,
    ).select_related('ruangan', 'ruangan_tambahan')


def aware_schedule_datetime(date_value, time_value):
    value = datetime.combine(date_value, time_value)
    return timezone.make_aware(value, timezone.get_current_timezone())


def get_checkin_window(schedule, date_value):
    starts_at = aware_schedule_datetime(date_value, schedule.waktu_mulai)
    ends_at = aware_schedule_datetime(date_value, schedule.get_waktu_selesai_efektif())
    opens_at = starts_at - timedelta(minutes=settings.ABSENSI_EARLY_CHECKIN_MINUTES)
    return opens_at, starts_at, ends_at


def validate_schedule_time(schedule, now=None):
    now = now or timezone.now()
    local_now = timezone.localtime(now)
    today = local_now.date()
    if schedule.hari != WEEKDAY_KEYS[today.weekday()]:
        return False, 'Jadwal praktikum bukan untuk hari ini.', None
    opens_at, starts_at, ends_at = get_checkin_window(schedule, today)
    if local_now < opens_at:
        return False, f'Absensi belum dibuka. Absensi dapat dilakukan mulai {opens_at:%H:%M}.', None
    if local_now > ends_at:
        return False, 'Jadwal praktikum sudah lewat.', None
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
