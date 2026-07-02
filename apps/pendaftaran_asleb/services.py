from datetime import timedelta

from django.utils import timezone

from apps.asleb.models import Asleb
from apps.pengguna.models import PengalamanPengguna, Pengguna

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
    expired_rows = list(expired.select_related('periode_aktif'))
    expired_nims = [item.nim for item in expired_rows]
    expired.update(status='nonaktif')

    users_by_nim = {
        item.nim_nik: item
        for item in Pengguna.objects.filter(nim_nik__in=expired_nims)
    }
    for asleb in expired_rows:
        pengguna = users_by_nim.get(asleb.nim)
        period = asleb.periode_aktif
        if not pengguna or not period:
            continue
        PengalamanPengguna.objects.update_or_create(
            source_key=f'aslab-period-{asleb.pk}-{period.pk}',
            defaults={
                'pengguna': pengguna,
                'jabatan': 'Asisten Laboratorium',
                'organisasi': 'Universitas Trisakti - LabHub',
                'tanggal_mulai': period.mulai,
                'tanggal_selesai': period.selesai,
                'masih_berjalan': False,
                'deskripsi': f'Mendampingi kegiatan praktikum {asleb.matkul or "laboratorium"}.',
                'otomatis': True,
            },
        )

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
    # Dua periode yang sudah diterima membuat pendaftaran berikutnya berlevel Senior.
    return ('senior', 2) if period_count >= 2 else ('junior', 1)


def get_period_registration_count(nim, period=None):
    period = period or get_current_period()
    return PendaftaranAsleb.objects.filter(nim=nim, periode=period).exclude(status='ditolak').count()
