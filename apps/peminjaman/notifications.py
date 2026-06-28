from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse

from apps.core.emails import send_branded_email
from apps.pengguna.models import Pengguna


def build_public_url(route_name, **kwargs):
    base_url = settings.PUBLIC_ACCESS_BASE_URL.rstrip('/') + '/'
    return urljoin(base_url, reverse(route_name, kwargs=kwargs).lstrip('/'))


def send_peminjaman_request_notifications(peminjaman):
    recipients = list(
        Pengguna.objects.filter(role__in=['admin', 'laboran'])
        .exclude(email='')
        .values_list('email', flat=True)
        .distinct()
    )
    if not recipients:
        return 0

    action_url = build_public_url('peminjaman:peminjaman_detail', pk=peminjaman.pk)
    text_body = (
        f'{peminjaman.nama_peminjam} mengajukan peminjaman {peminjaman.barang.nama}.\n'
        f'Kode: {peminjaman.kode_pinjam}\n'
        f'Tanggal: {peminjaman.tanggal_pinjam:%d-%m-%Y} sampai {peminjaman.tanggal_kembali:%d-%m-%Y}\n\n'
        f'Buka sistem: {action_url}'
    )
    return send_branded_email(
        subject='Pengajuan Peminjaman Alat Baru',
        recipients=recipients,
        text_body=text_body,
        title='Pengajuan peminjaman baru',
        greeting='Halo Admin dan Laboran,',
        intro=f'{peminjaman.nama_peminjam} mengajukan peminjaman alat laboratorium yang perlu ditinjau.',
        details=[
            {'label': 'Kode', 'value': peminjaman.kode_pinjam},
            {'label': 'Barang', 'value': peminjaman.barang.nama},
            {'label': 'Peminjam', 'value': peminjaman.nama_peminjam},
            {'label': 'Periode', 'value': f'{peminjaman.tanggal_pinjam:%d %b %Y} - {peminjaman.tanggal_kembali:%d %b %Y}'},
        ],
        action_url=action_url,
        action_label='Tinjau Pengajuan',
        fail_silently=True,
    )


def send_peminjaman_approved_notification(peminjaman):
    recipient = (
        Pengguna.objects.filter(nim_nik=peminjaman.nim)
        .exclude(email='')
        .values_list('email', flat=True)
        .first()
    )
    if not recipient:
        return 0

    action_url = build_public_url('peminjaman:peminjaman_detail', pk=peminjaman.pk)
    text_body = (
        f'Pengajuan peminjaman {peminjaman.barang.nama} sudah disetujui.\n'
        f'Kode: {peminjaman.kode_pinjam}\n'
        f'Status: {peminjaman.get_status_display()}\n'
        f'Tanggal pinjam: {peminjaman.tanggal_pinjam:%d-%m-%Y}\n'
        f'Tanggal kembali: {peminjaman.tanggal_kembali:%d-%m-%Y}\n\n'
        f'Buka sistem: {action_url}'
    )
    return send_branded_email(
        subject='Peminjaman Alat Disetujui',
        recipients=[recipient],
        text_body=text_body,
        title='Peminjaman disetujui',
        greeting=f'Halo {peminjaman.nama_peminjam},',
        intro='Pengajuan peminjaman alat Anda telah disetujui oleh pengelola laboratorium.',
        details=[
            {'label': 'Kode', 'value': peminjaman.kode_pinjam},
            {'label': 'Barang', 'value': peminjaman.barang.nama},
            {'label': 'Status', 'value': peminjaman.get_status_display()},
            {'label': 'Tanggal pinjam', 'value': f'{peminjaman.tanggal_pinjam:%d %b %Y}'},
            {'label': 'Tanggal kembali', 'value': f'{peminjaman.tanggal_kembali:%d %b %Y}'},
        ],
        action_url=action_url,
        action_label='Lihat Peminjaman',
        fail_silently=True,
    )
