from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

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

    return send_mail(
        subject='Pengajuan Peminjaman Alat Baru',
        message=(
            f'{peminjaman.nama_peminjam} mengajukan peminjaman {peminjaman.barang.nama}.\n'
            f'Kode: {peminjaman.kode_pinjam}\n'
            f'Tanggal: {peminjaman.tanggal_pinjam:%d-%m-%Y} sampai {peminjaman.tanggal_kembali:%d-%m-%Y}\n\n'
            f'Buka sistem: {build_public_url("peminjaman:peminjaman_detail", pk=peminjaman.pk)}'
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=recipients,
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

    return send_mail(
        subject='Peminjaman Alat Disetujui',
        message=(
            f'Pengajuan peminjaman {peminjaman.barang.nama} sudah disetujui.\n'
            f'Kode: {peminjaman.kode_pinjam}\n'
            f'Status: {peminjaman.get_status_display()}\n'
            f'Tanggal pinjam: {peminjaman.tanggal_pinjam:%d-%m-%Y}\n'
            f'Tanggal kembali: {peminjaman.tanggal_kembali:%d-%m-%Y}\n\n'
            f'Buka sistem: {build_public_url("peminjaman:peminjaman_detail", pk=peminjaman.pk)}'
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=[recipient],
        fail_silently=True,
    )
