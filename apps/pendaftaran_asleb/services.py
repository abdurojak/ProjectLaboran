from datetime import timedelta

from django.utils import timezone
from django.db import transaction

from apps.asleb.models import Asleb
from apps.pengguna.models import PengalamanPengguna, Pengguna

from .models import PendaftaranAsleb, PeriodeAsleb, RiwayatAsleb


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
    affected_matkul = [item.matkul for item in expired_rows if item.matkul]
    expired.update(status='nonaktif')

    if affected_matkul:
        from apps.jadwal.models import JadwalPraktikum, PermintaanPerubahanJadwal
        JadwalPraktikum.objects.filter(
            mata_kuliah__in=affected_matkul,
            status=JadwalPraktikum.STATUS_DIAJUKAN,
        ).update(status=JadwalPraktikum.STATUS_DITOLAK)
        PermintaanPerubahanJadwal.objects.filter(
            diajukan_oleh__nim_nik__in=expired_nims,
            status='diajukan',
        ).update(status='ditolak', diproses_pada=timezone.now())

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


@transaction.atomic
def end_asleb_period(period, ended_by, value=None):
    today = value or timezone.localdate()
    period.selesai = today - timedelta(days=1)
    if period.pendaftaran_selesai >= today:
        period.pendaftaran_selesai = today - timedelta(days=1)
    if period.pendaftaran_mulai > period.pendaftaran_selesai:
        period.pendaftaran_mulai = period.pendaftaran_selesai
    period.diakhiri_pada = timezone.now()
    period.diakhiri_oleh = ended_by
    period.save(update_fields=[
        'selesai', 'pendaftaran_mulai', 'pendaftaran_selesai',
        'diakhiri_pada', 'diakhiri_oleh', 'diperbarui_pada',
    ])
    return sync_expired_asleb_periods(today)


def get_asleb_experience(nim):
    period_ids = set(PendaftaranAsleb.objects.filter(
        nim=nim,
        status__in=['diterima', 'digenerate'],
        periode__isnull=False,
    ).values_list('periode_id', flat=True))
    period_ids.update(RiwayatAsleb.objects.filter(nim=nim).values_list('periode_id', flat=True))
    period_count = len(period_ids)
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
