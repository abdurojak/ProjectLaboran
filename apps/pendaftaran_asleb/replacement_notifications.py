import logging
from functools import wraps
from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse

from apps.asleb.models import HonorReassignment
from apps.core.emails import send_branded_email
from apps.kalender.realtime import send_user_notification
from apps.pengguna.models import Pengguna

from .models import AslabOffer, AslabReplacement


logger = logging.getLogger(__name__)


def _contained(function):
    @wraps(function)
    def wrapper(object_id):
        try:
            return function(object_id)
        except Exception:
            logger.exception(
                'Replacement notification callback failed for %s:%s',
                function.__name__, object_id,
            )
            return None
    return wrapper


def _public_dashboard_url():
    return urljoin(
        settings.PUBLIC_ACCESS_BASE_URL.rstrip('/') + '/',
        reverse('dashboard:home').lstrip('/'),
    )


def _laborans():
    return list(Pengguna.objects.filter(role='laboran', is_verified=True).order_by('pk'))


def _user_for_nim(nim):
    return Pengguna.objects.filter(nim_nik=nim, is_verified=True).first()


def _deliver(*, users, payload, subject, intro, details, event_id, note=None):
    recipients = []
    seen = set()
    for user in users:
        if not user or user.pk in seen:
            continue
        seen.add(user.pk)
        if user.email:
            recipients.append(user.email)
        try:
            send_user_notification(user.pk, payload)
        except Exception:
            logger.exception('Realtime replacement notification failed for event %s', event_id)

    if not recipients:
        return
    try:
        send_branded_email(
            subject=subject,
            recipients=recipients,
            text_body=f'{intro}\n\nBuka LabHub: {_public_dashboard_url()}',
            title=subject,
            intro=intro,
            details=details,
            action_url=_public_dashboard_url(),
            action_label='Buka LabHub',
            note=note,
            fail_silently=True,
        )
    except Exception:
        logger.exception('Email replacement notification failed for event %s', event_id)


def _replacement(replacement_id):
    return AslabReplacement.objects.select_related(
        'slot__matkul', 'slot__periode', 'outgoing_assignment__asleb',
        'incoming_assignment__asleb',
    ).filter(pk=replacement_id).first()


def _offer(offer_id):
    return AslabOffer.objects.select_related(
        'candidate', 'replacement__slot__matkul', 'replacement__slot__periode',
    ).filter(pk=offer_id).first()


def _course_details(replacement):
    return [
        {'label': 'Mata kuliah', 'value': str(replacement.slot.matkul)},
        {'label': 'Periode', 'value': str(replacement.slot.periode)},
        {'label': 'Slot', 'value': replacement.slot.nomor},
    ]


@_contained
def notify_assignment_ended(replacement_id):
    replacement = _replacement(replacement_id)
    if not replacement:
        return
    outgoing = _user_for_nim(replacement.outgoing_assignment.asleb.nim)
    payload = {
        'event': 'aslab.replacement.assignment_ended',
        'source_key': f'aslab-replacement:{replacement.pk}:assignment-ended',
        'title': 'Masa tugas aslab telah diakhiri',
        'message': f'Penugasan {replacement.slot.matkul} telah diakhiri dan proses penggantian dimulai.',
        'notification_type': 'warning',
        'related_object_id': replacement.pk,
        'related_url': reverse('dashboard:home'),
        'refresh_paths': ['/', '/kalender/notifikasi/'],
        'icon': 'user-round-x',
    }
    _deliver(
        users=[outgoing, *_laborans()], payload=payload,
        subject='Masa Tugas Aslab Diakhiri',
        intro='Masa tugas asisten laboratorium telah diakhiri dan slot memasuki proses penggantian.',
        details=_course_details(replacement), event_id=f'assignment-ended:{replacement.pk}',
    )


@_contained
def notify_offer_sent(offer_id):
    offer = _offer(offer_id)
    if not offer:
        return
    payload = {
        'event': 'aslab.replacement.offer_sent',
        'source_key': f'aslab-offer:{offer.pk}:sent',
        'title': 'Penawaran menjadi aslab pengganti',
        'message': f'Anda mendapat penawaran untuk {offer.replacement.slot.matkul}.',
        'notification_type': 'info',
        'related_object_id': offer.pk,
        'related_url': reverse('dashboard:home'),
        'refresh_paths': ['/', '/kalender/notifikasi/'],
        'icon': 'mail-check',
    }
    details = _course_details(offer.replacement) + [
        {'label': 'Batas respons', 'value': offer.deadline},
    ]
    _deliver(
        users=[offer.candidate], payload=payload, subject='Penawaran Aslab Pengganti',
        intro='Laboran menawarkan Anda untuk mengisi slot asisten laboratorium yang tersedia.',
        details=details, event_id=f'offer-sent:{offer.pk}',
    )


@_contained
def notify_offer_response(offer_id):
    offer = _offer(offer_id)
    if not offer:
        return
    status = offer.get_status_display()
    payload = {
        'event': 'aslab.replacement.offer_response',
        'source_key': f'aslab-offer:{offer.pk}:response:{offer.status}',
        'title': 'Respons penawaran aslab',
        'message': f'{offer.candidate.nama_pengguna} memberi respons: {status}.',
        'notification_type': 'success' if offer.status == AslabOffer.STATUS_ACCEPTED_INCOMPLETE else 'warning',
        'related_object_id': offer.pk,
        'related_url': reverse('dashboard:home'),
        'refresh_paths': ['/', '/kalender/notifikasi/'],
        'icon': 'message-square-check',
    }
    _deliver(
        users=[offer.candidate, *_laborans()], payload=payload,
        subject='Respons Penawaran Aslab',
        intro=f'Penawaran aslab pengganti telah direspons dengan status {status}.',
        details=_course_details(offer.replacement) + [{'label': 'Kandidat', 'value': offer.candidate.nama_pengguna}],
        event_id=f'offer-response:{offer.pk}:{offer.status}',
    )


@_contained
def notify_submission_ready(offer_id):
    offer = _offer(offer_id)
    if not offer:
        return
    payload = {
        'event': 'aslab.replacement.submission_ready',
        'source_key': f'aslab-offer:{offer.pk}:submission-ready',
        'title': 'Data kandidat siap diverifikasi',
        'message': f'Data {offer.candidate.nama_pengguna} siap ditinjau.',
        'notification_type': 'info',
        'related_object_id': offer.pk,
        'related_url': reverse('dashboard:home'),
        'refresh_paths': ['/', '/kalender/notifikasi/'],
        'icon': 'clipboard-check',
    }
    _deliver(
        users=_laborans(), payload=payload, subject='Data Kandidat Aslab Siap Diverifikasi',
        intro='Kandidat pengganti telah melengkapi data dan menunggu verifikasi laboran.',
        details=_course_details(offer.replacement) + [{'label': 'Kandidat', 'value': offer.candidate.nama_pengguna}],
        event_id=f'submission-ready:{offer.pk}',
    )


@_contained
def notify_submission_returned(offer_id):
    offer = _offer(offer_id)
    if not offer:
        return
    payload = {
        'event': 'aslab.replacement.submission_returned',
        'source_key': f'aslab-offer:{offer.pk}:submission-returned',
        'title': 'Data kandidat perlu diperbaiki',
        'message': 'Laboran mengembalikan data pendaftaran Anda untuk diperbaiki.',
        'notification_type': 'warning',
        'related_object_id': offer.pk,
        'related_url': reverse('dashboard:home'),
        'refresh_paths': ['/', '/kalender/notifikasi/'],
        'icon': 'file-warning',
    }
    _deliver(
        users=[offer.candidate], payload=payload, subject='Perbaikan Data Kandidat Aslab',
        intro='Data pendaftaran pengganti dikembalikan oleh laboran untuk diperbaiki.',
        details=_course_details(offer.replacement), event_id=f'submission-returned:{offer.pk}',
    )


@_contained
def notify_replacement_activated(replacement_id):
    replacement = _replacement(replacement_id)
    if not replacement:
        return
    incoming = (
        _user_for_nim(replacement.incoming_assignment.asleb.nim)
        if replacement.incoming_assignment_id else None
    )
    payload = {
        'event': 'aslab.replacement.activated',
        'source_key': f'aslab-replacement:{replacement.pk}:activated',
        'title': 'Aslab pengganti telah aktif',
        'message': f'Pengganti untuk {replacement.slot.matkul} telah diaktifkan.',
        'notification_type': 'success',
        'related_object_id': replacement.pk,
        'related_url': reverse('dashboard:home'),
        'refresh_paths': ['/', '/kalender/notifikasi/'],
        'icon': 'user-round-check',
    }
    _deliver(
        users=[incoming, *_laborans()], payload=payload, subject='Aslab Pengganti Telah Aktif',
        intro='Proses penggantian selesai dan asisten laboratorium baru telah aktif.',
        details=_course_details(replacement), event_id=f'activated:{replacement.pk}',
    )


@_contained
def notify_honor_correction_required(replacement_id):
    replacement = _replacement(replacement_id)
    if not replacement:
        return
    correction_count = HonorReassignment.objects.filter(
        replacement_id=replacement.pk,
        status=HonorReassignment.STATUS_CORRECTION_REQUIRED,
    ).count()
    if not correction_count:
        return
    payload = {
        'event': 'aslab.replacement.honor_correction_required',
        'source_key': f'aslab-replacement:{replacement.pk}:honor-correction',
        'title': 'Koreksi honor aslab diperlukan',
        'message': f'{correction_count} catatan honor memerlukan koreksi manual.',
        'notification_type': 'warning',
        'related_object_id': replacement.pk,
        'related_url': reverse('dashboard:home'),
        'refresh_paths': ['/', '/kalender/notifikasi/'],
        'icon': 'badge-alert',
    }
    _deliver(
        users=_laborans(), payload=payload, subject='Koreksi Honor Aslab Diperlukan',
        intro='Terdapat honor yang sudah dibayar atau diterbitkan dan memerlukan koreksi manual.',
        details=_course_details(replacement) + [{'label': 'Jumlah catatan', 'value': correction_count}],
        event_id=f'honor-correction:{replacement.pk}',
        note='Periksa arsip pembayaran sebelum melakukan koreksi manual.',
    )
