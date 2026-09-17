from datetime import datetime, timedelta

from django.db.models import Q

from apps.jadwal.models import JadwalPraktikum


def conflicting_practicum_schedules(event):
    if not event.ruangan_id or not event.waktu_selesai:
        return []
    days = [value for value, _ in JadwalPraktikum.HARI_CHOICES]
    weekday = event.tanggal.weekday()
    if weekday >= len(days):
        return []
    candidates = JadwalPraktikum.objects.filter(
        hari=days[weekday],
        status=JadwalPraktikum.STATUS_DITERIMA,
        waktu_mulai__lt=event.waktu_selesai,
    ).filter(
        Q(ruangan_id=event.ruangan_id) | Q(ruangan_tambahan_id=event.ruangan_id)
    )
    return [
        schedule for schedule in candidates
        if (schedule.waktu_selesai or (
            datetime.combine(event.tanggal, schedule.waktu_mulai) + timedelta(minutes=30)
        ).time()) > event.waktu_mulai
    ]
