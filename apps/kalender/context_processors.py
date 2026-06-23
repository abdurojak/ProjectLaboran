from datetime import timedelta

from django.utils import timezone
from django.urls import reverse

from .models import KegiatanKalender
from .utils import build_manual_notification, get_perayaan_notifications


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
    return {
        'kalender_notifications': notifications,
        'kalender_notification_count': len(notifications),
    }

