from datetime import timedelta

from django.utils import timezone

from apps.asleb.models import Asleb
from apps.pengguna.models import Pengguna

from .models import PendaftaranAsleb, PeriodeAsleb


def get_current_period(value=None):
    return PeriodeAsleb.get_for_date(value or timezone.localdate())


def is_registration_open(value=None):
    period = get_current_period(value)
    check_date = value or timezone.localdate()
    return period.pendaftaran_mulai <= check_date <= period.pendaftaran_selesai


def open_current_registration(days=30):
    today = timezone.localdate()
    period = get_current_period(today)
    period.pendaftaran_mulai = today
    period.pendaftaran_selesai = min(period.selesai, today + timedelta(days=days - 1))
    period.save(update_fields=['pendaftaran_mulai', 'pendaftaran_selesai', 'diperbarui_pada'])
    return period


def close_current_registration():
    today = timezone.localdate()
    period = get_current_period(today)
    period.pendaftaran_selesai = today - timedelta(days=1)
    if period.pendaftaran_mulai > period.pendaftaran_selesai:
        period.pendaftaran_mulai = period.pendaftaran_selesai
    period.save(update_fields=['pendaftaran_mulai', 'pendaftaran_selesai', 'diperbarui_pada'])
    return period


def sync_expired_asleb_periods(value=None):
    today = value or timezone.localdate()
    expired = Asleb.objects.filter(
        status='aktif',
        periode_aktif__isnull=False,
        periode_aktif__selesai__lt=today,
    )
    expired_nims = list(expired.values_list('nim', flat=True))
    expired.update(status='nonaktif')

    demoted = 0
    for pengguna in Pengguna.objects.filter(role='asisten_lab', nim_nik__in=expired_nims):
        has_active_period = Asleb.objects.filter(
            nim=pengguna.nim_nik,
            status='aktif',
            periode_aktif__mulai__lte=today,
            periode_aktif__selesai__gte=today,
        ).exists()
        if not has_active_period:
            pengguna.role = 'mahasiswa'
            pengguna.save(update_fields=['role', 'diperbarui_pada'])
            demoted += 1
    return len(expired_nims), demoted


def get_asleb_experience(nim):
    period_count = PendaftaranAsleb.objects.filter(
        nim=nim,
        status__in=['diterima', 'digenerate'],
        periode__isnull=False,
    ).values('periode_id').distinct().count()
    if not period_count:
        period_count = PendaftaranAsleb.objects.filter(
            nim=nim,
            status__in=['diterima', 'digenerate'],
            periode__isnull=True,
        ).count()
    return ('senior', 1) if period_count >= 3 else ('junior', 2)


def get_period_registration_count(nim, period=None):
    period = period or get_current_period()
    return PendaftaranAsleb.objects.filter(nim=nim, periode=period).exclude(status='ditolak').count()
