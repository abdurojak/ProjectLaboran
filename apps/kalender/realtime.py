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
        send_role_notification('admin', payload)

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
    send_role_notification('admin', payload)
