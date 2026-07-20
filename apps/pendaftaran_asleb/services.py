from datetime import date, timedelta
from urllib.parse import urljoin

from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.urls import reverse

from apps.asleb.models import (
    AbsensiAsleb,
    AbsensiMasukAsleb,
    Asleb,
    HonorAsleb,
    PengingatAbsensiAsleb,
    PengumpulanLaporanPraktikum,
    PesertaPraktikum,
    TugasLaporanPraktikum,
)
from apps.core.emails import send_branded_email
from apps.kalender.realtime import send_user_notification
from apps.pengguna.models import PengalamanPengguna, Pengguna

from .models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb, PeriodeAsleb, RiwayatAsleb


def get_current_period(value=None):
    return PeriodeAsleb.get_for_date(value or timezone.localdate())


def is_registration_open(value=None):
    period = get_current_period(value)
    check_date = value or timezone.localdate()
    setting = PengaturanPendaftaranAsleb.get_solo()
    return setting.dibuka and period.pendaftaran_mulai <= check_date <= period.pendaftaran_selesai


def open_current_registration(days=30):
    today = timezone.localdate()
    period = get_current_period(today)
    if period.selesai < today or period.diakhiri_pada:
        semester_end = date(today.year, 6, 30) if today.month <= 6 else date(today.year, 12, 31)
        period.mulai = today
        period.selesai = semester_end
        period.diakhiri_pada = None
        period.diakhiri_oleh = None
    period.pendaftaran_mulai = today
    period.pendaftaran_selesai = min(period.selesai, today + timedelta(days=days - 1))
    period.save(update_fields=[
        'mulai', 'selesai', 'pendaftaran_mulai', 'pendaftaran_selesai',
        'diakhiri_pada', 'diakhiri_oleh', 'diperbarui_pada',
    ])
    return period


def close_current_registration():
    today = timezone.localdate()
    period = get_current_period(today)
    period.pendaftaran_selesai = today - timedelta(days=1)
    if period.pendaftaran_mulai > period.pendaftaran_selesai:
        period.pendaftaran_mulai = period.pendaftaran_selesai
    period.save(update_fields=['pendaftaran_mulai', 'pendaftaran_selesai', 'diperbarui_pada'])
    return period


def _build_public_url(route_name, **kwargs):
    base_url = settings.PUBLIC_ACCESS_BASE_URL.rstrip('/') + '/'
    return urljoin(base_url, reverse(route_name, kwargs=kwargs).lstrip('/'))


def _append_matkul_to_description(existing_description, matkul):
    if not matkul:
        return existing_description or 'Menyelesaikan penugasan sebagai Asisten Laboratorium.'

    current = (existing_description or '').strip()
    if not current:
        return f'Menyelesaikan penugasan sebagai Asisten Laboratorium untuk mata kuliah {matkul}.'

    if str(matkul) in current:
        return current

    if 'Mata kuliah:' in current:
        return f'{current}, {matkul}'
    return f'{current} Mata kuliah: {matkul}.'


def record_asleb_experience(pengguna, asleb, period=None):
    if not pengguna:
        return None

    period = period or asleb.periode_aktif
    end_date = getattr(period, 'selesai', None) or timezone.localdate()
    start_date = getattr(period, 'mulai', None) or asleb.tanggal_bergabung or end_date
    month_key = end_date.strftime('%Y-%m')
    source_key = f'aslab-experience:{pengguna.pk}:{month_key}'
    defaults = {
        'pengguna': pengguna,
        'jabatan': 'Asisten Laboratorium',
        'organisasi': 'Universitas Trisakti - LabHub',
        'tanggal_mulai': start_date,
        'tanggal_selesai': end_date,
        'masih_berjalan': False,
        'deskripsi': _append_matkul_to_description('', asleb.matkul or 'laboratorium'),
        'otomatis': True,
    }
    experience, created = PengalamanPengguna.objects.update_or_create(
        source_key=source_key,
        defaults=defaults,
    )
    if not created:
        changed_fields = []
        merged_description = _append_matkul_to_description(experience.deskripsi, asleb.matkul)
        if experience.deskripsi != merged_description:
            experience.deskripsi = merged_description
            changed_fields.append('deskripsi')
        if experience.tanggal_mulai > start_date:
            experience.tanggal_mulai = start_date
            changed_fields.append('tanggal_mulai')
        if experience.tanggal_selesai != end_date:
            experience.tanggal_selesai = end_date
            changed_fields.append('tanggal_selesai')
        if experience.masih_berjalan:
            experience.masih_berjalan = False
            changed_fields.append('masih_berjalan')
        if changed_fields:
            experience.save(update_fields=changed_fields + ['diperbarui_pada'])
    return experience


def deactivate_asleb_membership(asleb, *, forced=False, reason='', acted_by=None, today=None):
    today = today or timezone.localdate()
    normalized_reason = (reason or '').strip()
    active_rows = list(Asleb.objects.filter(nim=asleb.nim, status='aktif').select_related('periode_aktif'))
    if not active_rows and asleb.status != 'aktif':
        active_rows = [asleb]

    Asleb.objects.filter(pk__in=[item.pk for item in active_rows]).update(status='nonaktif')

    if normalized_reason:
        timestamp_label = timezone.localtime().strftime('%d %b %Y %H:%M')
        actor_label = acted_by.nama_pengguna if acted_by else 'Sistem LabHub'
        note_line = f'Dinonaktifkan pada {timestamp_label} oleh {actor_label}. Alasan: {normalized_reason}'
        for row in active_rows:
            updated_note = '\n'.join(filter(None, [row.catatan.strip(), note_line]))
            if updated_note != row.catatan:
                row.catatan = updated_note
                row.save(update_fields=['catatan', 'diperbarui_pada'])

    akun = Pengguna.objects.filter(nim_nik=asleb.nim).first()
    if akun and akun.role == 'asisten_lab':
        has_other_active = Asleb.objects.filter(
            nim=asleb.nim,
            status='aktif',
        ).exclude(pk__in=[item.pk for item in active_rows]).exists()
        if not has_other_active:
            akun.role = 'mahasiswa'
            akun.save(update_fields=['role', 'diperbarui_pada'])

    experience = None
    if akun and not forced:
        for row in active_rows:
            experience = record_asleb_experience(akun, row, row.periode_aktif) or experience

    return {
        'akun': akun,
        'active_rows': active_rows,
        'experience': experience,
    }


def notify_manual_asleb_removal(asleb, pengguna, *, reason, acted_by=None):
    if not pengguna:
        return 0

    actor_name = acted_by.nama_pengguna if acted_by else 'Laboran'
    related_url = reverse('dashboard:home')
    payload = {
        'event': 'asleb.membership.removed',
        'source_key': f'asleb-removed:{asleb.pk}:{pengguna.pk}',
        'title': 'Status Asisten Lab dinonaktifkan',
        'message': f'Akses Asisten Lab Anda dihentikan. Alasan: {reason}',
        'notification_type': 'warning',
        'related_object_id': asleb.pk,
        'related_url': related_url,
        'refresh_paths': ['/', '/kalender/notifikasi/'],
        'icon': 'user-round-x',
        'icon_class': 'bg-rose-50 text-rose-700',
    }
    send_user_notification(pengguna.pk, payload)

    if not pengguna.email:
        return 0

    action_url = _build_public_url('dashboard:home')
    text_body = (
        f'Halo {pengguna.nama_pengguna},\n\n'
        f'Status Asisten Lab Anda telah dinonaktifkan oleh {actor_name}.\n'
        f'Alasan: {reason}\n\n'
        f'Buka portal: {action_url}'
    )
    return send_branded_email(
        subject='Status Asisten Lab Dinonaktifkan',
        recipients=[pengguna.email],
        text_body=text_body,
        title='Status Asisten Lab dinonaktifkan',
        greeting=f'Halo {pengguna.nama_pengguna},',
        intro=f'Akses Asisten Lab Anda telah dihentikan oleh {actor_name}.',
        details=[
            {'label': 'Nama', 'value': asleb.nama},
            {'label': 'NIM', 'value': asleb.nim},
            {'label': 'Alasan', 'value': reason},
        ],
        action_url=action_url,
        action_label='Buka LabHub',
        note='Penonaktifan manual ini tidak ditambahkan ke bagian pengalaman otomatis.',
        fail_silently=True,
    )


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
    affected_matkul_ids = list(PendaftaranAsleb.objects.filter(
        nim__in=expired_nims,
        periode__in=[item.periode_aktif for item in expired_rows if item.periode_aktif_id],
        matkul__isnull=False,
    ).values_list('matkul_id', flat=True).distinct())
    affected_matkul_ids.extend(RiwayatAsleb.objects.filter(
        nim__in=expired_nims,
        periode__in=[item.periode_aktif for item in expired_rows if item.periode_aktif_id],
        matkul__isnull=False,
    ).values_list('matkul_id', flat=True).distinct())
    if affected_matkul:
        affected_labels = set(affected_matkul)
        affected_matkul_ids.extend([
            matkul.pk
            for matkul in MataKuliahAsleb.objects.all()
            if str(matkul) in affected_labels
        ])
    affected_matkul_ids = list(set(affected_matkul_ids))
    expired.update(status='nonaktif')

    expired_honor_qs = HonorAsleb.objects.filter(asleb__nim__in=expired_nims).exclude(status='dibayar')
    for honor in expired_honor_qs:
        changed_fields = []
        if not honor.diarsipkan_pada:
            honor.diarsipkan_pada = timezone.now()
            changed_fields.append('diarsipkan_pada')
        note = 'Diarsipkan saat periode Asisten Lab berakhir; pembayaran tetap menunggu konfirmasi dan bukti transfer.'
        existing_note = (honor.keterangan or '').strip()
        if note not in existing_note:
            honor.keterangan = f'{existing_note} {note}'.strip()
            changed_fields.append('keterangan')
        if changed_fields:
            honor.save(update_fields=changed_fields + ['diperbarui_pada'])

    if expired_rows:
        expired_row_ids = [item.pk for item in expired_rows]
        AbsensiAsleb.objects.filter(asleb_id__in=expired_row_ids).delete()
        AbsensiMasukAsleb.objects.filter(asleb_id__in=expired_row_ids).delete()
        PengingatAbsensiAsleb.objects.filter(asleb_id__in=expired_row_ids).delete()

    if affected_matkul or affected_matkul_ids:
        from apps.jadwal.models import JadwalPraktikum, PermintaanPerubahanJadwal
        PengumpulanLaporanPraktikum.objects.filter(tugas__matkul_id__in=affected_matkul_ids).delete()
        TugasLaporanPraktikum.objects.filter(matkul_id__in=affected_matkul_ids).delete()
        JadwalPraktikum.objects.filter(
            mata_kuliah__in=affected_matkul,
        ).delete()
        PermintaanPerubahanJadwal.objects.filter(
            diajukan_oleh__nim_nik__in=expired_nims,
        ).delete()

    users_by_nim = {
        item.nim_nik: item
        for item in Pengguna.objects.filter(nim_nik__in=expired_nims)
    }
    for asleb in expired_rows:
        pengguna = users_by_nim.get(asleb.nim)
        period = asleb.periode_aktif
        if not pengguna or not period:
            continue
        record_asleb_experience(pengguna, asleb, period)

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
    if expired_nims:
        PesertaPraktikum.objects.all().delete()
    return len(expired_nims), demoted


@transaction.atomic
def end_asleb_period(period, ended_by, value=None):
    today = value or timezone.localdate()
    period = PeriodeAsleb.objects.select_for_update().get(pk=period.pk)
    if period.diakhiri_pada:
        return 0, 0
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
