from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.urls import reverse
from django.utils import timezone

from apps.pengguna.models import Pengguna

from .models import Notifikasi


def user_group_name(user_id):
    return f'user_{int(user_id)}'


def role_group_name(role):
    safe_role = ''.join(character for character in str(role) if character.isalnum() or character == '_')
    return f'role_{safe_role}'


def _normalized_payload(payload):
    now = timezone.now()
    result = {
        'event': payload.get('event', 'notification.created'),
        'source_key': payload.get('source_key'),
        'title': payload.get('title', 'Pembaruan LabHub'),
        'message': payload.get('message', ''),
        'notification_type': payload.get('notification_type', 'info'),
        'related_url': payload.get('related_url', ''),
        'related_object_id': payload.get('related_object_id'),
        'refresh_paths': payload.get('refresh_paths', []),
        'icon': payload.get('icon', 'bell-ring'),
        'icon_class': payload.get('icon_class', 'bg-brand-50 text-brand-700'),
        'created_at': payload.get('created_at', now.isoformat()),
    }
    return result


def _persist_notification(pengguna, payload):
    now = timezone.now()
    source_key = payload.get('source_key') or (
        f'realtime:{payload["event"]}:{payload.get("related_object_id") or now.timestamp()}'
    )
    notification, _ = Notifikasi.objects.update_or_create(
        pengguna=pengguna,
        source_key=source_key[:160],
        defaults={
            'judul': payload['title'][:220],
            'deskripsi': payload['message'],
            'tanggal': timezone.localdate(),
            'waktu_label': timezone.localtime(now).strftime('%H:%M'),
            'lokasi': '',
            'url': payload.get('related_url', '')[:240],
            'badge': payload.get('notification_type', 'info')[:50],
            'icon': payload.get('icon', 'bell-ring')[:50],
            'icon_class': payload.get('icon_class', 'bg-brand-50 text-brand-700')[:120],
            'source_updated_at': now,
            'dibaca_pada': None,
        },
    )
    payload['notification_id'] = notification.pk
    payload['unread_count'] = Notifikasi.objects.filter(
        pengguna=pengguna,
        dibaca_pada__isnull=True,
    ).count()


def _group_send(group_name, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(group_name, {
        'type': 'realtime.event',
        'payload': payload,
    })


def send_user_notification(user_id, payload, persist=True):
    pengguna = Pengguna.objects.filter(pk=user_id, is_verified=True).first()
    if not pengguna:
        return False
    normalized = _normalized_payload(payload)
    if persist:
        _persist_notification(pengguna, normalized)
    _group_send(user_group_name(pengguna.pk), normalized)
    return True


def send_role_notification(role, payload, persist=True):
    normalized = _normalized_payload(payload)
    if persist:
        for pengguna in Pengguna.objects.filter(role=role, is_verified=True):
            personalized = normalized.copy()
            _persist_notification(pengguna, personalized)
            _group_send(user_group_name(pengguna.pk), personalized)
    else:
        _group_send(role_group_name(role), normalized)
    return True


def users_for_nim(nim):
    return Pengguna.objects.filter(nim_nik=nim, is_verified=True)


def send_registration_status_update(pendaftaran):
    status_label = pendaftaran.get_status_display()
    payload = {
        'event': 'registration.status_changed',
        'source_key': f'pendaftaran-realtime:{pendaftaran.pk}:{pendaftaran.status}',
        'title': f'Status pendaftaran: {status_label}',
        'message': f'Pendaftaran {pendaftaran.matkul} kini berstatus {status_label}.',
        'notification_type': pendaftaran.status,
        'related_object_id': pendaftaran.pk,
        'related_url': reverse('dashboard:home'),
        'refresh_paths': ['/pendaftaran-asleb/', '/'],
    }
    for pengguna in users_for_nim(pendaftaran.nim):
        send_user_notification(pengguna.pk, payload)


def send_schedule_update(jadwal, event='schedule.updated', notify_managers=False):
    payload = {
        'event': event,
        'source_key': f'jadwal-realtime:{jadwal.pk}:{event}:{jadwal.status}',
        'title': 'Pembaruan jadwal praktikum',
        'message': f'{jadwal.mata_kuliah} - {jadwal.get_hari_display()} {jadwal.waktu_mulai:%H:%M}.',
        'notification_type': jadwal.status,
        'related_object_id': jadwal.pk,
        'related_url': reverse('jadwal:jadwal_detail', kwargs={'pk': jadwal.pk}),
        'refresh_paths': ['/jadwal/', '/'],
    }
    if notify_managers:
        send_role_notification('laboran', payload)

    from apps.pendaftaran_asleb.models import PendaftaranAsleb, RiwayatAsleb
    nims = set()
    for registration in PendaftaranAsleb.objects.select_related('matkul').filter(status__in=['diterima', 'digenerate']):
        if str(registration.matkul) == jadwal.mata_kuliah:
            nims.add(registration.nim)
    for history in RiwayatAsleb.objects.select_related('matkul').all():
        if str(history.matkul) == jadwal.mata_kuliah:
            nims.add(history.nim)
    for pengguna in Pengguna.objects.filter(nim_nik__in=nims, is_verified=True):
        send_user_notification(pengguna.pk, payload)

    for role in ('mahasiswa', 'asisten_lab'):
        _group_send(role_group_name(role), _normalized_payload({**payload, 'source_key': None}))


def send_honor_update(honor, event='honor.updated'):
    payload = {
        'event': event,
        'source_key': f'honor-realtime:{honor.pk}:{event}:{honor.status}',
        'title': 'Honor Asisten Lab diperbarui',
        'message': f'Honor {honor.bulan:%B %Y}: {honor.jumlah_rupiah}.',
        'notification_type': honor.status,
        'related_object_id': honor.pk,
        'related_url': reverse('asleb:honor_list'),
        'refresh_paths': ['/asleb/honorarium/', '/'],
    }
    for pengguna in users_for_nim(honor.asleb.nim):
        send_user_notification(pengguna.pk, payload)


def send_attendance_update(absensi):
    payload = {
        'event': 'attendance.created',
        'source_key': f'absensi-realtime:{absensi.pk}',
        'title': 'Absensi Asisten Lab tercatat',
        'message': f'{absensi.asleb.nama} menyimpan absensi Modul {absensi.modul}.',
        'notification_type': 'success',
        'related_object_id': absensi.pk,
        'related_url': reverse('asleb:absensi_list'),
        'refresh_paths': ['/asleb/absensi/', '/'],
    }
    for pengguna in users_for_nim(absensi.asleb.nim):
        send_user_notification(pengguna.pk, payload)
    send_role_notification('laboran', payload)


def send_peminjaman_request_update(peminjaman):
    payload = {
        'event': 'peminjaman.request.created',
        'source_key': f'peminjaman-admin:{peminjaman.pk}:diajukan',
        'title': f'Pengajuan peminjaman baru: {peminjaman.barang.nama}',
        'message': f'{peminjaman.nama_peminjam} mengajukan peminjaman alat dan menunggu persetujuan.',
        'notification_type': 'diajukan',
        'related_object_id': peminjaman.pk,
        'related_url': reverse('peminjaman:peminjaman_detail', kwargs={'pk': peminjaman.pk}),
        'refresh_paths': ['/peminjaman/', '/kalender/notifikasi/', '/'],
        'icon': 'clipboard-list',
        'icon_class': 'bg-amber-50 text-amber-700',
    }
    send_role_notification('laboran', payload)


def send_peminjaman_status_update(peminjaman):
    status_label = peminjaman.get_status_display()
    status_meta = {
        'ditolak': ('Peminjaman ditolak', 'Pengajuan peminjaman Anda belum dapat disetujui.', 'x-circle', 'bg-rose-50 text-rose-700'),
        'dipinjam': ('Peminjaman disetujui', 'Pengajuan peminjaman alat Anda telah disetujui.', 'check-circle-2', 'bg-blue-50 text-blue-700'),
        'dikembalikan': ('Peminjaman selesai', 'Barang telah dicatat kembali ke laboratorium.', 'undo-2', 'bg-emerald-50 text-emerald-700'),
        'hilang': ('Barang ditandai hilang', 'Barang pada peminjaman Anda ditandai hilang dan perlu ditindaklanjuti.', 'circle-alert', 'bg-rose-50 text-rose-700'),
        'rusak': ('Barang ditandai rusak', 'Barang pada peminjaman Anda ditandai rusak dan perlu ditindaklanjuti.', 'wrench', 'bg-orange-50 text-orange-700'),
        'digantikan': ('Penggantian barang tercatat', 'Penggantian barang pada peminjaman Anda telah dicatat.', 'refresh-cw', 'bg-brand-50 text-brand-700'),
    }
    title, message, icon, icon_class = status_meta.get(
        peminjaman.status,
        ('Status peminjaman diperbarui', 'Status peminjaman alat Anda telah diperbarui.', 'bell-ring', 'bg-brand-50 text-brand-700'),
    )
    payload = {
        'event': 'peminjaman.status.updated',
        'source_key': f'peminjaman:{peminjaman.pk}:{peminjaman.status}',
        'title': title,
        'message': f'{message} Barang: {peminjaman.barang.nama}.',
        'notification_type': status_label,
        'related_object_id': peminjaman.pk,
        'related_url': reverse('peminjaman:peminjaman_detail', kwargs={'pk': peminjaman.pk}),
        'refresh_paths': ['/peminjaman/', '/kalender/notifikasi/', '/'],
        'icon': icon,
        'icon_class': icon_class,
    }
    for pengguna in users_for_nim(peminjaman.nim):
        send_user_notification(pengguna.pk, payload)
