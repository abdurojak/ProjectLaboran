from datetime import timedelta

from django.utils import timezone

from .models import KegiatanKalender


def kalender_notifikasi(request):
    today = timezone.localdate()
    limit_date = today + timedelta(days=7)
    notifications = list(
        KegiatanKalender.objects.filter(
            tampilkan_notifikasi=True,
            tanggal__gte=today,
            tanggal__lte=limit_date,
        )
        .order_by('tanggal', 'waktu_mulai')[:5]
    )
    return {
        'kalender_notifications': notifications,
        'kalender_notification_count': len(notifications),
    }

