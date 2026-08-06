from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse
from django.utils.formats import date_format

from apps.core.emails import send_branded_email
from apps.pengguna.models import Pengguna

from .models import HonorAsleb


def _public_url(route_name):
    base_url = settings.PUBLIC_ACCESS_BASE_URL.rstrip('/') + '/'
    return urljoin(base_url, reverse(route_name).lstrip('/'))


def send_honor_paid_email(honor_id):
    """Notify the related assistant only after a payment is committed."""
    honor = HonorAsleb.objects.select_related('asleb').filter(
        pk=honor_id,
        status='dibayar',
    ).first()
    if not honor:
        return 0

    account_emails = list(Pengguna.objects.filter(
        nim_nik=honor.asleb.nim,
        is_verified=True,
    ).exclude(email='').values_list('email', flat=True))
    email_candidates = account_emails or [honor.asleb.email]
    recipients = sorted({
        email.strip().lower()
        for email in email_candidates
        if email and email.strip()
    })
    if not recipients:
        return 0

    period_label = date_format(honor.bulan, 'F Y')
    transfer_date = date_format(honor.tanggal_transfer, 'd F Y')
    action_url = _public_url('asleb:honor_list')
    text_body = (
        f'Halo {honor.asleb.nama},\n\n'
        f'Honor Asisten Lab periode {period_label} telah ditransfer.\n'
        f'Honor sebelum potongan: {honor.honor_sebelum_potongan_rupiah}\n'
        f'Biaya admin: {honor.biaya_admin_rupiah}\n'
        f'Honor bersih: {honor.jumlah_rupiah}\n'
        f'Tanggal transfer: {transfer_date}\n'
        f'PIC transfer: {honor.pic_transfer}\n\n'
        f'Lihat rincian honor: {action_url}'
    )
    return send_branded_email(
        subject=f'Honor Asisten Lab {period_label} Sudah Ditransfer',
        recipients=recipients,
        text_body=text_body,
        title='Honor Anda sudah ditransfer',
        greeting=f'Halo {honor.asleb.nama},',
        intro='Pembayaran honor Asisten Laboratorium Anda telah dikonfirmasi oleh pengelola laboratorium.',
        eyebrow='Pembayaran Honor Aslab',
        details=[
            {'label': 'Periode', 'value': period_label},
            {'label': 'Sebelum potongan', 'value': honor.honor_sebelum_potongan_rupiah},
            {'label': 'Biaya admin', 'value': honor.biaya_admin_rupiah},
            {'label': 'Honor diterima', 'value': honor.jumlah_rupiah},
            {'label': 'Metode', 'value': honor.get_metode_transfer_display()},
            {'label': 'Tanggal transfer', 'value': transfer_date},
            {'label': 'PIC transfer', 'value': honor.pic_transfer},
        ],
        action_url=action_url,
        action_label='Lihat Rincian Honor',
        highlight=honor.jumlah_rupiah,
        note='Simpan bukti pembayaran yang tersedia pada halaman rincian honor. Hubungi laboran jika dana belum diterima.',
        fail_silently=True,
    )
