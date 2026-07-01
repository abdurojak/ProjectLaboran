from datetime import datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone

from apps.jadwal.models import JadwalPraktikum
from apps.peminjaman.models import PeminjamanAlat
from apps.pendaftaran_asleb.models import PendaftaranAsleb, PengaturanPendaftaranAsleb
from apps.pendaftaran_asleb.utils import get_public_registration_url

from .models import KegiatanKalender, Notifikasi
from .utils import build_manual_notification, get_perayaan_notifications


PEMINJAMAN_NOTIFICATION_STATUSES = ['ditolak', 'dipinjam', 'dikembalikan', 'hilang', 'rusak', 'digantikan']
JADWAL_PRAKTIKUM_NOTIFICATION_STATUSES = [
    JadwalPraktikum.STATUS_DITERIMA,
    JadwalPraktikum.STATUS_DITOLAK,
]


def get_aslab_matkul_labels(pengguna):
    if not pengguna or pengguna.role != 'asisten_lab':
        return []

    matkul_values = PendaftaranAsleb.objects.filter(
        nim=pengguna.nim_nik,
        status__in=['diterima', 'digenerate'],
    ).select_related('matkul').values_list(
        'matkul__nama',
        'matkul__dosen',
        'matkul__kelas',
    )
    return [f'{nama} - {dosen} - {kelas}' for nama, dosen, kelas in matkul_values]


def sync_user_notifications(pengguna):
    if not pengguna:
        return

    for payload in build_notification_payloads(pengguna):
        upsert_notification(pengguna, payload)


def build_notification_payloads(pengguna):
    today = timezone.localdate()
    limit_date = today + timedelta(days=7)
    payloads = []

    kegiatan_list = (
        KegiatanKalender.objects.filter(
            tampilkan_notifikasi=True,
            tanggal__gte=today,
            tanggal__lte=limit_date,
        )
        .order_by('tanggal', 'waktu_mulai')
    )
    for kegiatan in kegiatan_list:
        if not kegiatan.visible_for(pengguna):
            continue
        payload = build_manual_notification(
            kegiatan,
            reverse('kalender:kegiatan_detail', kwargs={'pk': kegiatan.pk}),
        )
        payload.update({
            'source_key': f'kalender:{kegiatan.pk}',
            'source_updated_at': kegiatan.diperbarui_pada,
        })
        payloads.append(payload)

    for payload in get_perayaan_notifications(today):
        payload.update({
            'source_key': f'perayaan:{payload["tanggal"].isoformat()}:{payload["judul"]}',
            'source_updated_at': make_aware_datetime(payload['tanggal']),
        })
        payloads.append(payload)

    payloads.extend(build_peminjaman_notifications(pengguna))
    payloads.extend(build_pendaftaran_aslab_notifications(pengguna))
    payloads.extend(build_jadwal_praktikum_notifications(pengguna))
    return payloads


def build_peminjaman_notifications(pengguna):
    if pengguna.role in {'admin', 'laboran'}:
        return build_admin_peminjaman_request_notifications()

    if pengguna.role not in {'mahasiswa', 'asisten_lab'}:
        return []

    status_meta = {
        'ditolak': {
            'badge': 'Ditolak',
            'icon': 'x-circle',
            'icon_class': 'bg-rose-50 text-rose-700',
            'description': 'Pengajuan peminjaman Anda belum dapat disetujui oleh pengelola laboratorium.',
        },
        'dipinjam': {
            'badge': 'Dipinjam',
            'icon': 'check-circle-2',
            'icon_class': 'bg-blue-50 text-blue-700',
            'description': 'Pengajuan peminjaman Anda sudah disetujui dan barang tercatat sedang dipinjam.',
        },
        'dikembalikan': {
            'badge': 'Dikembalikan',
            'icon': 'undo-2',
            'icon_class': 'bg-emerald-50 text-emerald-700',
            'description': 'Peminjaman Anda sudah ditandai selesai dan barang kembali tersedia.',
        },
        'hilang': {
            'badge': 'Hilang',
            'icon': 'circle-alert',
            'icon_class': 'bg-rose-50 text-rose-700',
            'description': 'Peminjaman Anda ditandai hilang dan perlu tindak lanjut dari laboratorium.',
        },
        'rusak': {
            'badge': 'Rusak',
            'icon': 'wrench',
            'icon_class': 'bg-orange-50 text-orange-700',
            'description': 'Peminjaman Anda ditandai rusak dan perlu tindak lanjut dari laboratorium.',
        },
        'digantikan': {
            'badge': 'Digantikan',
            'icon': 'refresh-cw',
            'icon_class': 'bg-brand-50 text-brand-700',
            'description': 'Barang pada peminjaman Anda sudah ditandai digantikan.',
        },
    }
    payloads = []
    peminjaman_list = (
        PeminjamanAlat.objects.select_related('barang', 'barang__lokasi')
        .filter(nim=pengguna.nim_nik, status__in=status_meta.keys())
        .order_by('-diperbarui_pada')
    )

    for peminjaman in peminjaman_list:
        meta = status_meta[peminjaman.status]
        payloads.append({
            'source_key': f'peminjaman:{peminjaman.pk}:{peminjaman.status}',
            'judul': f'Status peminjaman {peminjaman.barang.nama}: {meta["badge"]}',
            'deskripsi': meta['description'],
            'tanggal': peminjaman.diperbarui_pada.date(),
            'waktu_label': peminjaman.diperbarui_pada.strftime('%H:%M'),
            'lokasi': peminjaman.barang.lokasi.nama_lokasi if peminjaman.barang.lokasi_id else '-',
            'url': reverse('peminjaman:peminjaman_detail', kwargs={'pk': peminjaman.pk}),
            'badge': meta['badge'],
            'icon': meta['icon'],
            'icon_class': meta['icon_class'],
            'source_updated_at': peminjaman.diperbarui_pada,
        })
    return payloads


def build_admin_peminjaman_request_notifications():
    payloads = []
    peminjaman_list = (
        PeminjamanAlat.objects.select_related('barang', 'barang__lokasi')
        .filter(status='diajukan')
        .order_by('-dibuat_pada')
    )
    for peminjaman in peminjaman_list:
        payloads.append({
            'source_key': f'peminjaman-admin:{peminjaman.pk}:diajukan',
            'judul': f'Pengajuan peminjaman baru: {peminjaman.barang.nama}',
            'deskripsi': f'{peminjaman.nama_peminjam} mengajukan peminjaman alat dan menunggu persetujuan.',
            'tanggal': peminjaman.dibuat_pada.date(),
            'waktu_label': peminjaman.dibuat_pada.strftime('%H:%M'),
            'lokasi': peminjaman.barang.lokasi.nama_lokasi if peminjaman.barang.lokasi_id else '-',
            'url': reverse('peminjaman:peminjaman_detail', kwargs={'pk': peminjaman.pk}),
            'badge': 'Diajukan',
            'icon': 'clipboard-list',
            'icon_class': 'bg-amber-50 text-amber-700',
            'source_updated_at': peminjaman.dibuat_pada,
        })
    return payloads


def build_pendaftaran_aslab_notifications(pengguna):
    payloads = []
    if pengguna.role == 'mahasiswa':
        pengaturan = PengaturanPendaftaranAsleb.get_solo()
        if pengaturan.dibuka:
            title = 'Pendaftaran aslab sedang dibuka'
            description = 'Form pendaftaran asisten laboratorium sudah tersedia. Silakan lengkapi data diri, berkas, rekening, dan pilihan mata kuliah.'
            icon = 'user-plus'
            icon_class = 'bg-emerald-50 text-emerald-700'
            url = get_public_registration_url()
            badge = 'Dibuka'
        else:
            title = 'Pendaftaran aslab sudah ditutup'
            description = 'Form pendaftaran asisten laboratorium sudah ditutup. Silakan menunggu informasi pembukaan periode berikutnya.'
            icon = 'lock'
            icon_class = 'bg-slate-100 text-slate-600'
            url = ''
            badge = 'Ditutup'
        payloads.append({
            'source_key': f'pendaftaran-aslab-setting:{pengaturan.pk}:{pengaturan.dibuka}',
            'judul': title,
            'deskripsi': description,
            'tanggal': pengaturan.diperbarui_pada.date(),
            'waktu_label': pengaturan.diperbarui_pada.strftime('%H:%M'),
            'lokasi': 'Lab JTIF Usakti',
            'url': url,
            'badge': badge,
            'icon': icon,
            'icon_class': icon_class,
            'source_updated_at': pengaturan.diperbarui_pada,
        })

    if pengguna.role not in {'mahasiswa', 'asisten_lab'}:
        return payloads

    statuses = ['diterima', 'ditolak']
    if pengguna.role == 'asisten_lab':
        statuses.append('digenerate')

    pendaftaran_list = (
        PendaftaranAsleb.objects.select_related('matkul')
        .filter(nim=pengguna.nim_nik, status__in=statuses)
        .order_by('-diperbarui_pada')
    )
    for pendaftaran in pendaftaran_list:
        if pendaftaran.status == 'digenerate':
            title = 'Pendaftaran aslab Anda masuk Data Aslab'
            description = f'Selamat, data aslab untuk {pendaftaran.matkul} sudah dibuat. Akun Anda dapat mengakses fitur aslab sesuai hak akses yang berlaku.'
            badge = 'Data Aslab'
            icon = 'id-card'
            icon_class = 'bg-emerald-50 text-emerald-700'
        elif pendaftaran.status == 'ditolak':
            title = 'Pendaftaran aslab Anda ditolak'
            description = f'Pengajuan asisten laboratorium untuk {pendaftaran.matkul} belum dapat diterima pada periode ini.'
            badge = 'Ditolak'
            icon = 'badge-x'
            icon_class = 'bg-rose-50 text-rose-700'
        else:
            title = 'Pendaftaran aslab Anda diterima'
            description = f'Selamat, pengajuan asisten laboratorium untuk {pendaftaran.matkul} sudah diterima. Silakan menunggu arahan berikutnya dari laboratorium.'
            badge = 'Diterima'
            icon = 'badge-check'
            icon_class = 'bg-emerald-50 text-emerald-700'
        payloads.append({
            'source_key': f'pendaftaran-aslab:{pendaftaran.pk}:{pendaftaran.status}',
            'judul': title,
            'deskripsi': description,
            'tanggal': pendaftaran.diperbarui_pada.date(),
            'waktu_label': pendaftaran.diperbarui_pada.strftime('%H:%M'),
            'lokasi': 'Lab JTIF Usakti',
            'url': '',
            'badge': badge,
            'icon': icon,
            'icon_class': icon_class,
            'source_updated_at': pendaftaran.diperbarui_pada,
        })
    return payloads


def build_jadwal_praktikum_notifications(pengguna):
    labels = get_aslab_matkul_labels(pengguna)
    if not labels:
        return []

    status_meta = {
        JadwalPraktikum.STATUS_DITERIMA: {
            'title': 'Jadwal praktikum Anda diterima',
            'badge': 'Diterima',
            'icon': 'calendar-check',
            'icon_class': 'bg-emerald-50 text-emerald-700',
            'description': 'sudah diterima dan tampil di jadwal resmi laboratorium.',
        },
        JadwalPraktikum.STATUS_DITOLAK: {
            'title': 'Jadwal praktikum Anda ditolak',
            'badge': 'Ditolak',
            'icon': 'calendar-x',
            'icon_class': 'bg-rose-50 text-rose-700',
            'description': 'belum dapat disetujui oleh pengelola laboratorium.',
        },
    }
    payloads = []
    jadwal_list = (
        JadwalPraktikum.objects.select_related('ruangan')
        .filter(mata_kuliah__in=labels, status__in=JADWAL_PRAKTIKUM_NOTIFICATION_STATUSES)
        .order_by('-diperbarui_pada')
    )
    for jadwal in jadwal_list:
        meta = status_meta[jadwal.status]
        waktu_mulai = jadwal.waktu_mulai.strftime('%H:%M')
        waktu_selesai = jadwal.get_waktu_selesai_efektif().strftime('%H:%M')
        payloads.append({
            'source_key': f'jadwal-praktikum:{jadwal.pk}:{jadwal.status}',
            'judul': meta['title'],
            'deskripsi': f'Jadwal praktikum {jadwal.mata_kuliah} {meta["description"]}',
            'tanggal': jadwal.diperbarui_pada.date(),
            'waktu_label': f'{jadwal.get_hari_display()}, {waktu_mulai}-{waktu_selesai}',
            'lokasi': jadwal.ruangan.nama,
            'url': reverse('jadwal:jadwal_detail', kwargs={'pk': jadwal.pk}),
            'badge': meta['badge'],
            'icon': meta['icon'],
            'icon_class': meta['icon_class'],
            'source_updated_at': jadwal.diperbarui_pada,
        })
    return payloads


def upsert_notification(pengguna, payload):
    source_updated_at = payload['source_updated_at']
    dibaca_pada = None
    if pengguna.notifikasi_dibaca_pada and source_updated_at <= pengguna.notifikasi_dibaca_pada:
        dibaca_pada = pengguna.notifikasi_dibaca_pada
    defaults = {
        'judul': payload['judul'],
        'deskripsi': payload.get('deskripsi', ''),
        'tanggal': payload['tanggal'],
        'waktu_label': payload.get('waktu_label', ''),
        'lokasi': payload.get('lokasi', ''),
        'url': payload.get('url', ''),
        'badge': payload.get('badge', ''),
        'icon': payload.get('icon', 'bell'),
        'icon_class': payload.get('icon_class', 'bg-slate-100 text-slate-600'),
        'source_updated_at': source_updated_at,
    }
    notification, created = Notifikasi.objects.get_or_create(
        pengguna=pengguna,
        source_key=payload['source_key'],
        defaults={**defaults, 'dibaca_pada': dibaca_pada},
    )
    if created:
        return notification

    should_mark_unread = source_updated_at > notification.source_updated_at
    for field, value in defaults.items():
        setattr(notification, field, value)
    if should_mark_unread:
        notification.dibaca_pada = None
    elif dibaca_pada and not notification.dibaca_pada:
        notification.dibaca_pada = dibaca_pada
    notification.save()
    return notification


def make_aware_datetime(value):
    return timezone.make_aware(datetime.combine(value, time.min))
