from datetime import timedelta

from django.utils import timezone
from django.urls import reverse

from .models import KegiatanKalender, Notifikasi
from .notifications import sync_user_notifications
from .utils import build_manual_notification, get_perayaan_notifications


def get_unread_peminjaman_notification_count(pengguna):
    if not pengguna:
        return 0

    sync_user_notifications(pengguna)
    return Notifikasi.objects.filter(
        pengguna=pengguna,
        dibaca_pada__isnull=True,
        source_key__startswith='peminjaman',
    ).count()


def get_unread_pendaftaran_asleb_acceptance_count(pengguna):
    if not pengguna:
        return 0

    sync_user_notifications(pengguna)
    return Notifikasi.objects.filter(
        pengguna=pengguna,
        dibaca_pada__isnull=True,
        source_key__startswith='pendaftaran-aslab',
    ).count()

def get_unread_jadwal_praktikum_acceptance_count(pengguna):
    if not pengguna:
        return 0

    sync_user_notifications(pengguna)
    return Notifikasi.objects.filter(
        pengguna=pengguna,
        dibaca_pada__isnull=True,
        source_key__startswith='jadwal-praktikum',
    ).count()


def get_unread_notification_count(pengguna):
    if not pengguna:
        return 0

    sync_user_notifications(pengguna)
    return Notifikasi.objects.filter(
        pengguna=pengguna,
        dibaca_pada__isnull=True,
    ).exclude(
        source_key__startswith='kalender:',
    ).exclude(
        source_key__startswith='perayaan:',
    ).count()


def kalender_notifikasi(request):
    today = timezone.localdate()
    limit_date = today + timedelta(days=7)
    kegiatan_notifications = list(
        KegiatanKalender.objects.filter(
            tampilkan_notifikasi=True,
            tanggal__gte=today,
            tanggal__lte=limit_date,
        )
        .order_by('tanggal', 'waktu_mulai')[:5]
    )
    manual_notifications = [
        build_manual_notification(
            kegiatan,
            reverse('kalender:kegiatan_detail', kwargs={'pk': kegiatan.pk}),
        )
        for kegiatan in kegiatan_notifications
    ]
    notifications = sorted(
        manual_notifications + get_perayaan_notifications(today),
        key=lambda item: (item['tanggal'], item['judul']),
    )[:5]
    current_pengguna = getattr(request, 'current_pengguna', None)
    unread_notification_count = get_unread_notification_count(current_pengguna)

    return {
        'kalender_notifications': notifications,
        'kalender_notification_count': len(notifications),
        'unread_notification_count': unread_notification_count,
    }

