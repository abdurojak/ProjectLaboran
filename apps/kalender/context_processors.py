from datetime import timedelta

from django.utils import timezone
from django.urls import reverse

from apps.peminjaman.models import PeminjamanAlat
from apps.pendaftaran_asleb.models import PendaftaranAsleb, PengaturanPendaftaranAsleb

from .models import KegiatanKalender
from .utils import build_manual_notification, get_perayaan_notifications


PEMINJAMAN_NOTIFICATION_STATUSES = ['dipinjam', 'dikembalikan', 'hilang', 'rusak', 'digantikan']


def get_unread_peminjaman_notification_count(pengguna):
    if not pengguna:
        return 0

    if pengguna.role in {'admin', 'laboran'}:
        queryset = PeminjamanAlat.objects.filter(status='diajukan')

        if pengguna.notifikasi_dibaca_pada:
            queryset = queryset.filter(dibuat_pada__gt=pengguna.notifikasi_dibaca_pada)

        return queryset.count()

    if pengguna.role not in {'mahasiswa', 'asisten_lab'}:
        return 0

    queryset = PeminjamanAlat.objects.filter(
        nim=pengguna.nim_nik,
        status__in=PEMINJAMAN_NOTIFICATION_STATUSES,
    )

    if pengguna.notifikasi_dibaca_pada:
        queryset = queryset.filter(diperbarui_pada__gt=pengguna.notifikasi_dibaca_pada)

    return queryset.count()


def get_unread_pendaftaran_asleb_acceptance_count(pengguna):
    if not pengguna or pengguna.role != 'mahasiswa':
        return 0

    queryset = PendaftaranAsleb.objects.filter(
        nim=pengguna.nim_nik,
        status='diterima',
    )

    if pengguna.notifikasi_dibaca_pada:
        queryset = queryset.filter(diperbarui_pada__gt=pengguna.notifikasi_dibaca_pada)

    return queryset.count()


def get_unread_notification_count(pengguna):
    if not pengguna:
        return 0

    unread_count = get_unread_peminjaman_notification_count(pengguna)

    if pengguna.role != 'mahasiswa':
        return unread_count

    unread_count += get_unread_pendaftaran_asleb_acceptance_count(pengguna)

    pengaturan_pendaftaran = PengaturanPendaftaranAsleb.get_solo()
    if (
        not pengguna.notifikasi_dibaca_pada
        or pengaturan_pendaftaran.diperbarui_pada > pengguna.notifikasi_dibaca_pada
    ):
        unread_count += 1

    return unread_count


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

