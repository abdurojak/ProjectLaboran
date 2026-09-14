from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse

from apps.core.emails import send_branded_email
from apps.kalender.realtime import send_user_notification, users_for_nim
from apps.pengguna.models import Pengguna


def build_public_url(route_name, **kwargs):
    base_url = settings.PUBLIC_ACCESS_BASE_URL.rstrip('/') + '/'
    return urljoin(base_url, reverse(route_name, kwargs=kwargs).lstrip('/'))


def send_peminjaman_request_notifications(peminjaman):
    recipients = list(
        Pengguna.objects.filter(role='laboran')
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
        greeting='Halo Laboran,',
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


def send_peminjaman_status_notification(peminjaman):
    status_messages = {
        'ditolak': ('Peminjaman Alat Ditolak', 'Peminjaman ditolak', 'Pengajuan peminjaman alat Anda belum dapat disetujui.'),
        'dipinjam': ('Peminjaman Alat Disetujui', 'Peminjaman disetujui', 'Pengajuan peminjaman alat Anda telah disetujui.'),
        'dikembalikan': ('Peminjaman Alat Dikembalikan', 'Peminjaman selesai', 'Barang telah dicatat kembali ke laboratorium.'),
        'hilang': ('Status Peminjaman: Hilang', 'Barang ditandai hilang', 'Barang pada peminjaman Anda ditandai hilang dan perlu ditindaklanjuti.'),
        'rusak': ('Status Peminjaman: Rusak', 'Barang ditandai rusak', 'Barang pada peminjaman Anda ditandai rusak dan perlu ditindaklanjuti.'),
        'digantikan': ('Status Peminjaman: Digantikan', 'Penggantian barang tercatat', 'Penggantian barang pada peminjaman Anda telah dicatat.'),
    }
    subject, title, intro = status_messages.get(
        peminjaman.status,
        ('Status Peminjaman Alat Diperbarui', 'Status peminjaman diperbarui', 'Status peminjaman alat Anda telah diperbarui.'),
    )
    related_url = reverse('peminjaman:peminjaman_detail', kwargs={'pk': peminjaman.pk})
    action_url = build_public_url('peminjaman:peminjaman_detail', pk=peminjaman.pk)
    realtime_payload = {
        'event': 'peminjaman.status_changed',
        'source_key': f'peminjaman:{peminjaman.pk}:{peminjaman.status}',
        'title': title,
        'message': f'{intro} Barang: {peminjaman.barang.nama}.',
        'notification_type': peminjaman.status,
        'related_object_id': peminjaman.pk,
        'related_url': related_url,
        'refresh_paths': ['/peminjaman/', '/kalender/notifikasi/', '/'],
        'icon': 'package-check' if peminjaman.status == 'dikembalikan' else ('x-circle' if peminjaman.status == 'ditolak' else 'bell-ring'),
        'icon_class': 'bg-emerald-50 text-emerald-700' if peminjaman.status == 'dikembalikan' else ('bg-rose-50 text-rose-700' if peminjaman.status == 'ditolak' else 'bg-amber-50 text-amber-700'),
        'auto_refresh': True,
    }
    for pengguna in users_for_nim(peminjaman.nim):
        send_user_notification(pengguna.pk, realtime_payload)

    recipient = (
        Pengguna.objects.filter(nim_nik=peminjaman.nim)
        .exclude(email='')
        .values_list('email', flat=True)
        .first()
    )
    if not recipient:
        return 0

    text_body = (
        f'Status peminjaman {peminjaman.barang.nama} diperbarui.\n'
        f'Kode: {peminjaman.kode_pinjam}\n'
        f'Status: {peminjaman.get_status_display()}\n'
        f'Tanggal pinjam: {peminjaman.tanggal_pinjam:%d-%m-%Y}\n'
        f'Tanggal kembali: {peminjaman.tanggal_kembali:%d-%m-%Y}\n\n'
        f'Buka sistem: {action_url}'
    )
    return send_branded_email(
        subject=subject,
        recipients=[recipient],
        text_body=text_body,
        title=title,
        greeting=f'Halo {peminjaman.nama_peminjam},',
        intro=intro,
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


def send_peminjaman_approved_notification(peminjaman):
    return send_peminjaman_status_notification(peminjaman)


def send_extension_request_notifications(extension):
    recipients = list(
        Pengguna.objects.filter(role='asisten_lab')
        .exclude(pk=extension.diajukan_oleh_id)
        .exclude(email='')
        .values_list('email', flat=True)
        .distinct()
    )
    if not recipients:
        return 0

    anchor = extension.transaksi.detail.select_related('barang').first()
    if not anchor:
        return 0
    action_url = build_public_url('peminjaman:peminjaman_detail', pk=anchor.pk)
    return send_branded_email(
        subject='Pengajuan Perpanjangan Peminjaman Alat',
        recipients=recipients,
        text_body=(
            f'{extension.transaksi.nama_peminjam} mengajukan perpanjangan peminjaman '
            f'{extension.transaksi.kode_pinjam}.\n'
            f'Dari {extension.tanggal_kembali_sebelumnya:%d-%m-%Y} sampai '
            f'{extension.tanggal_kembali_diminta:%d-%m-%Y}.\n'
            f'Alasan: {extension.alasan}\n'
            f'Kondisi barang: {extension.get_kondisi_barang_display()}\n'
            f'Keterangan kondisi: {extension.keterangan_kondisi or "-"}\n'
            f'Pernyataan kejujuran: {"Disetujui" if extension.pernyataan_jujur else "Belum tercatat"}'
            f'\n\nTinjau pengajuan: {action_url}'
        ),
        title='Perpanjangan perlu ditinjau',
        greeting='Halo Asisten Lab,',
        intro='Ada pengajuan perpanjangan peminjaman alat yang memerlukan persetujuan.',
        details=[
            {'label': 'Kode', 'value': extension.transaksi.kode_pinjam},
            {'label': 'Peminjam', 'value': extension.transaksi.nama_peminjam},
            {'label': 'Tanggal lama', 'value': f'{extension.tanggal_kembali_sebelumnya:%d %b %Y}'},
            {'label': 'Tanggal diminta', 'value': f'{extension.tanggal_kembali_diminta:%d %b %Y}'},
            {'label': 'Alasan', 'value': extension.alasan},
            {'label': 'Kondisi barang', 'value': extension.get_kondisi_barang_display()},
            {'label': 'Keterangan kondisi', 'value': extension.keterangan_kondisi or '-'},
            {
                'label': 'Pernyataan kejujuran',
                'value': 'Disetujui' if extension.pernyataan_jujur else 'Belum tercatat',
            },
        ],
        action_url=action_url,
        action_label='Tinjau Perpanjangan',
        note='Pengajuan tidak mengubah tanggal kembali sebelum disetujui.',
        fail_silently=True,
    )


def send_extension_status_notification(extension):
    recipient = extension.diajukan_oleh.email
    if not recipient:
        return 0
    anchor = extension.transaksi.detail.first()
    if not anchor:
        return 0
    approved = extension.status == 'disetujui'
    action_url = build_public_url('peminjaman:peminjaman_detail', pk=anchor.pk)
    status_label = extension.get_status_display()
    return send_branded_email(
        subject=f'Perpanjangan Peminjaman {status_label}',
        recipients=[recipient],
        text_body=(
            f'Pengajuan perpanjangan {extension.transaksi.kode_pinjam} {status_label.lower()}.\n'
            f'Tanggal kembali: {(extension.tanggal_kembali_disetujui or extension.tanggal_kembali_sebelumnya):%d-%m-%Y}.\n'
            f'Catatan: {extension.catatan_peninjau or "-"}\n\nBuka sistem: {action_url}'
        ),
        title=f'Perpanjangan {status_label.lower()}',
        greeting=f'Halo {extension.transaksi.nama_peminjam},',
        intro=(
            'Tanggal kembali peminjaman Anda telah diperbarui.'
            if approved else 'Pengajuan perpanjangan Anda belum dapat disetujui.'
        ),
        details=[
            {'label': 'Kode', 'value': extension.transaksi.kode_pinjam},
            {'label': 'Status', 'value': status_label},
            {
                'label': 'Tanggal kembali',
                'value': f'{(extension.tanggal_kembali_disetujui or extension.tanggal_kembali_sebelumnya):%d %b %Y}',
            },
            {'label': 'Catatan peninjau', 'value': extension.catatan_peninjau or '-'},
        ],
        action_url=action_url,
        action_label='Lihat Peminjaman',
        fail_silently=True,
    )


def send_due_reminder_notification(transaksi, *, overdue=False):
    recipient = (
        Pengguna.objects.filter(nim_nik=transaksi.nim)
        .exclude(email='')
        .values_list('email', flat=True)
        .first()
    )
    anchor = transaksi.detail.first()
    if not recipient or not anchor:
        return 0
    action_url = build_public_url('peminjaman:peminjaman_detail', pk=anchor.pk)
    title = 'Peminjaman terlambat' if overdue else 'Pengingat pengembalian alat'
    intro = (
        'Peminjaman Anda telah melewati tanggal kembali. Skor kredit akan berkurang sampai barang dikembalikan.'
        if overdue
        else 'Masa peminjaman Anda segera berakhir. Kembalikan tepat waktu untuk menjaga skor kredit.'
    )
    return send_branded_email(
        subject=title,
        recipients=[recipient],
        text_body=(
            f'{intro}\nKode: {transaksi.kode_pinjam}\n'
            f'Tanggal kembali: {transaksi.tanggal_kembali:%d-%m-%Y}\n\n'
            f'Jika memerlukan tambahan waktu, ajukan perpanjangan: {action_url}'
        ),
        title=title,
        greeting=f'Halo {transaksi.nama_peminjam},',
        intro=intro,
        details=[
            {'label': 'Kode', 'value': transaksi.kode_pinjam},
            {'label': 'Tanggal kembali', 'value': f'{transaksi.tanggal_kembali:%d %b %Y}'},
            {'label': 'Status', 'value': 'Terlambat' if overdue else 'Segera jatuh tempo'},
        ],
        action_url=action_url,
        action_label='Ajukan Perpanjangan',
        note='Perpanjangan hanya berlaku setelah disetujui oleh Asisten Lab.',
        fail_silently=True,
    )
