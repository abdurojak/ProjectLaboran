from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse

from apps.core.emails import send_branded_email
from apps.pendaftaran_asleb.models import PendaftaranAsleb, RiwayatAsleb


def send_jadwal_status_notification(jadwal):
    registrations = PendaftaranAsleb.objects.select_related('matkul').filter(
        status__in=['diterima', 'digenerate'],
    ).exclude(email='')
    recipients = sorted({
        item.email
        for item in registrations
        if str(item.matkul) == jadwal.mata_kuliah
    })
    history = RiwayatAsleb.objects.select_related('matkul').exclude(email='')
    recipients.extend(item.email for item in history if str(item.matkul) == jadwal.mata_kuliah)
    recipients = sorted(set(recipients))
    if not recipients:
        return 0

    accepted = jadwal.status == jadwal.STATUS_DITERIMA
    status_label = 'Diterima' if accepted else 'Ditolak'
    action_url = urljoin(
        settings.PUBLIC_ACCESS_BASE_URL.rstrip('/') + '/',
        reverse('jadwal:jadwal_detail', kwargs={'pk': jadwal.pk}).lstrip('/'),
    )
    intro = (
        'Pengajuan jadwal praktikum telah disetujui dan masuk ke jadwal resmi.'
        if accepted else
        'Pengajuan jadwal praktikum belum dapat disetujui. Silakan koordinasikan jadwal pengganti.'
    )
    return send_branded_email(
        subject=f'Jadwal Praktikum {status_label}',
        recipients=recipients,
        text_body=(
            f'{intro}\n\nMata kuliah: {jadwal.mata_kuliah}\n'
            f'Waktu: {jadwal.get_hari_display()}, {jadwal.waktu_mulai:%H:%M}\n'
            f'Ruangan: {jadwal.get_display_ruangan_nama()}\n\nDetail: {action_url}'
        ),
        title=f'Jadwal praktikum {status_label.lower()}',
        greeting='Halo Asisten Laboratorium,',
        intro=intro,
        details=[
            {'label': 'Mata kuliah', 'value': jadwal.mata_kuliah},
            {'label': 'Waktu', 'value': f'{jadwal.get_hari_display()}, {jadwal.waktu_mulai:%H:%M}'},
            {'label': 'Ruangan', 'value': jadwal.get_display_ruangan_nama()},
            {'label': 'Status', 'value': status_label},
        ],
        action_url=action_url,
        action_label='Lihat Jadwal',
        highlight=status_label,
        fail_silently=True,
    )
