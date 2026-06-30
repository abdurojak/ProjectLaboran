from datetime import datetime, timedelta

from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.asleb.models import Asleb
from apps.core.views import PostOnlyDeleteMixin
from apps.jadwal.models import JadwalPraktikum
from apps.peminjaman.models import PeminjamanAlat
from apps.pendaftaran_asleb.models import PendaftaranAsleb, PengaturanPendaftaranAsleb
from apps.pendaftaran_asleb.utils import get_public_registration_url

from .forms import KegiatanKalenderForm
from .models import KegiatanKalender
from .utils import build_manual_notification, get_perayaan_calendar_events, get_perayaan_notifications


DAY_TO_FULLCALENDAR = {
    'senin': 1,
    'selasa': 2,
    'rabu': 3,
    'kamis': 4,
    'jumat': 5,
    'sabtu': 6,
}


def get_visible_kegiatan_queryset(pengguna):
    queryset = KegiatanKalender.objects.select_related('dibuat_oleh')
    if not pengguna or pengguna.role in {'admin', 'laboran'}:
        return queryset

    return queryset.filter(
        Q(dibuat_oleh=pengguna) |
        Q(target_role__contains=pengguna.role) |
        Q(dibuat_oleh__isnull=True, target_role='')
    )


def get_manageable_kegiatan_queryset(pengguna):
    queryset = KegiatanKalender.objects.select_related('dibuat_oleh')
    if not pengguna or pengguna.role in {'admin', 'laboran'}:
        return queryset

    return queryset.filter(dibuat_oleh=pengguna)


def parse_asleb_matkul(matkul_text):
    parts = [part.strip() for part in matkul_text.split(' - ') if part.strip()]
    if not parts:
        return '', ''

    mata_kuliah = parts[0]
    kelas = parts[-1] if len(parts) >= 3 else ''
    return mata_kuliah, kelas


def get_asisten_lab_jadwal_queryset(pengguna):
    if not pengguna or pengguna.role != 'asisten_lab':
        return JadwalPraktikum.objects.none()

    asleb_list = Asleb.objects.filter(nim=pengguna.nim_nik, status='aktif').exclude(matkul='')
    query = Q()

    for asleb in asleb_list:
        mata_kuliah, kelas = parse_asleb_matkul(asleb.matkul)
        if mata_kuliah and kelas:
            query |= Q(mata_kuliah__iexact=mata_kuliah, kelas__iexact=kelas)
        elif mata_kuliah:
            query |= Q(mata_kuliah__iexact=mata_kuliah)

    if not query:
        return JadwalPraktikum.objects.none()

    return JadwalPraktikum.objects.select_related('ruangan', 'ruangan_tambahan').filter(query).distinct()


def get_global_jadwal_queryset():
    return JadwalPraktikum.objects.select_related('ruangan', 'ruangan_tambahan').filter(
        status__in=[JadwalPraktikum.STATUS_DIAJUKAN, JadwalPraktikum.STATUS_DITERIMA]
    ).order_by('hari', 'waktu_mulai', 'mata_kuliah')


def build_jadwal_calendar_events(jadwal_queryset):
    events = []
    for jadwal in jadwal_queryset:
        day_number = DAY_TO_FULLCALENDAR.get(jadwal.hari)
        if not day_number:
            continue

        is_pending = jadwal.status == JadwalPraktikum.STATUS_DIAJUKAN
        end_time = jadwal.waktu_selesai or jadwal.waktu_mulai
        events.append({
            'title': f'Praktikum {jadwal.mata_kuliah} - {jadwal.kelas}',
            'daysOfWeek': [day_number],
            'startTime': jadwal.waktu_mulai.strftime('%H:%M:%S'),
            'endTime': end_time.strftime('%H:%M:%S'),
            'backgroundColor': '#f59e0b' if is_pending else '#0f766e',
            'borderColor': '#d97706' if is_pending else '#0f766e',
            'textColor': '#ffffff',
            'extendedProps': {
                'lokasi': jadwal.get_display_ruangan_nama() if jadwal.ruangan_id else '-',
                'notifikasi': (
                    'Jadwal praktikum otomatis (menunggu persetujuan)'
                    if is_pending else
                    'Jadwal praktikum otomatis (disetujui)'
                ),
            },
        })
    return events


class KegiatanKalenderListView(ListView):
    model = KegiatanKalender
    template_name = 'kalender/kegiatan_list.html'
    context_object_name = 'kegiatan_list'

    def get_queryset(self):
        pengguna = getattr(self.request, 'current_pengguna', None)
        return get_visible_kegiatan_queryset(pengguna).order_by('tanggal', 'waktu_mulai')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        calendar_events = []

        for kegiatan in context['kegiatan_list']:
            start_dt = datetime.combine(kegiatan.tanggal, kegiatan.waktu_mulai)
            end_time = kegiatan.waktu_selesai or kegiatan.waktu_mulai
            end_dt = datetime.combine(kegiatan.tanggal, end_time)
            if end_dt <= start_dt:
                end_dt = start_dt + timedelta(hours=1)

            calendar_events.append(
                {
                    'title': kegiatan.judul,
                    'start': start_dt.isoformat(),
                    'end': end_dt.isoformat(),
                    'url': reverse_lazy('kalender:kegiatan_detail', kwargs={'pk': kegiatan.pk}),
                    'backgroundColor': '#1d4ed8' if kegiatan.tampilkan_notifikasi else '#64748b',
                    'borderColor': '#1d4ed8' if kegiatan.tampilkan_notifikasi else '#64748b',
                    'textColor': '#ffffff',
                    'extendedProps': {
                        'lokasi': kegiatan.lokasi or '-',
                        'notifikasi': 'Aktif' if kegiatan.tampilkan_notifikasi else 'Nonaktif',
                    },
                }
            )

        pengguna = getattr(self.request, 'current_pengguna', None)
        jadwal_praktikum_otomatis = get_global_jadwal_queryset()
        jadwal_praktikum_saya = get_asisten_lab_jadwal_queryset(pengguna)
        calendar_events.extend(build_jadwal_calendar_events(jadwal_praktikum_otomatis))
        calendar_events.extend(get_perayaan_calendar_events(timezone.localdate().year))

        context['calendar_events'] = calendar_events
        context['upcoming_kegiatan'] = context['kegiatan_list'][:5]
        context['jadwal_praktikum_saya'] = jadwal_praktikum_saya
        context['jadwal_praktikum_otomatis'] = jadwal_praktikum_otomatis[:5]
        return context


class KegiatanKalenderDetailView(DetailView):
    model = KegiatanKalender
    template_name = 'kalender/kegiatan_detail.html'
    context_object_name = 'kegiatan'

    def get_queryset(self):
        pengguna = getattr(self.request, 'current_pengguna', None)
        return get_visible_kegiatan_queryset(pengguna)


class KegiatanKalenderCreateView(CreateView):
    model = KegiatanKalender
    form_class = KegiatanKalenderForm
    template_name = 'kalender/kegiatan_form.html'
    success_url = reverse_lazy('kalender:kegiatan_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return kwargs

    def form_valid(self, form):
        pengguna = getattr(self.request, 'current_pengguna', None)
        form.instance.dibuat_oleh = pengguna
        if not pengguna or pengguna.role not in {'admin', 'laboran'}:
            form.instance.target_role = ''
        return super().form_valid(form)


class KegiatanKalenderUpdateView(UpdateView):
    model = KegiatanKalender
    form_class = KegiatanKalenderForm
    template_name = 'kalender/kegiatan_form.html'
    success_url = reverse_lazy('kalender:kegiatan_list')

    def get_queryset(self):
        pengguna = getattr(self.request, 'current_pengguna', None)
        return get_manageable_kegiatan_queryset(pengguna)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return kwargs

    def form_valid(self, form):
        pengguna = getattr(self.request, 'current_pengguna', None)
        if not pengguna or pengguna.role not in {'admin', 'laboran'}:
            form.instance.target_role = ''
        return super().form_valid(form)


class KegiatanKalenderDeleteView(PostOnlyDeleteMixin, DeleteView):
    model = KegiatanKalender
    template_name = 'kalender/kegiatan_confirm_delete.html'
    context_object_name = 'kegiatan'
    success_url = reverse_lazy('kalender:kegiatan_list')

    def get_queryset(self):
        pengguna = getattr(self.request, 'current_pengguna', None)
        return get_manageable_kegiatan_queryset(pengguna)


class NotifikasiListView(ListView):
    model = KegiatanKalender
    template_name = 'kalender/notifikasi_list.html'
    context_object_name = 'notifikasi_list'
    notifications_per_page = 20

    def get_queryset(self):
        today = timezone.localdate()
        limit_date = today + timedelta(days=7)
        pengguna = getattr(self.request, 'current_pengguna', None)
        return (
            get_visible_kegiatan_queryset(pengguna).filter(
                tampilkan_notifikasi=True,
                tanggal__gte=today,
                tanggal__lte=limit_date,
            )
            .order_by('tanggal', 'waktu_mulai')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        manual_notifications = [
            build_manual_notification(
                kegiatan,
                reverse('kalender:kegiatan_detail', kwargs={'pk': kegiatan.pk}),
            )
            for kegiatan in context['notifikasi_list']
        ]
        perayaan_notifications = get_perayaan_notifications(today)
        peminjaman_notifications = self.get_peminjaman_notifications()
        pendaftaran_asleb_notifications = self.get_pendaftaran_asleb_notifications()
        pendaftaran_asleb_acceptance_notifications = self.get_pendaftaran_asleb_acceptance_notifications()
        notifications = sorted(
            (
                manual_notifications
                + perayaan_notifications
                + peminjaman_notifications
                + pendaftaran_asleb_notifications
                + pendaftaran_asleb_acceptance_notifications
            ),
            key=lambda item: (item['tanggal'], item.get('waktu_label', ''), item['judul']),
            reverse=True,
        )
        paginator = Paginator(notifications, self.notifications_per_page)
        page_obj = paginator.get_page(self.request.GET.get('page'))
        context['notifikasi_list'] = page_obj.object_list
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        self.mark_notifications_as_read()
        return context

    def mark_notifications_as_read(self):
        pengguna = getattr(self.request, 'current_pengguna', None)
        if not pengguna:
            return

        pengguna.notifikasi_dibaca_pada = timezone.now()
        pengguna.save(update_fields=['notifikasi_dibaca_pada', 'diperbarui_pada'])

    def get_peminjaman_notifications(self):
        pengguna = getattr(self.request, 'current_pengguna', None)
        if not pengguna:
            return []

        if pengguna.role in {'admin', 'laboran'}:
            return self.get_admin_peminjaman_request_notifications(pengguna)

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

        peminjaman_list = (
            PeminjamanAlat.objects.select_related('barang')
            .filter(nim=pengguna.nim_nik, status__in=status_meta.keys())
            .order_by('-diperbarui_pada')
        )
        notifications = []

        for peminjaman in peminjaman_list:
            meta = status_meta[peminjaman.status]
            is_read = bool(
                pengguna.notifikasi_dibaca_pada
                and peminjaman.diperbarui_pada <= pengguna.notifikasi_dibaca_pada
            )
            notifications.append({
                'judul': f'Status peminjaman {peminjaman.barang.nama}: {meta["badge"]}',
                'deskripsi': meta['description'],
                'tanggal': peminjaman.diperbarui_pada.date(),
                'waktu_label': peminjaman.diperbarui_pada.strftime('%H:%M'),
                'lokasi': peminjaman.barang.lokasi.nama_lokasi if peminjaman.barang.lokasi_id else '-',
                'url': reverse('peminjaman:peminjaman_detail', kwargs={'pk': peminjaman.pk}),
                'badge': meta['badge'],
                'icon': meta['icon'],
                'icon_class': meta['icon_class'],
                'is_read': is_read,
            })

        return notifications

    def get_admin_peminjaman_request_notifications(self, pengguna):
        peminjaman_list = (
            PeminjamanAlat.objects.select_related('barang', 'barang__lokasi')
            .filter(status='diajukan')
            .order_by('-dibuat_pada')
        )
        notifications = []

        for peminjaman in peminjaman_list:
            is_read = bool(
                pengguna.notifikasi_dibaca_pada
                and peminjaman.dibuat_pada <= pengguna.notifikasi_dibaca_pada
            )
            notifications.append({
                'judul': f'Pengajuan peminjaman baru: {peminjaman.barang.nama}',
                'deskripsi': f'{peminjaman.nama_peminjam} mengajukan peminjaman alat dan menunggu persetujuan.',
                'tanggal': peminjaman.dibuat_pada.date(),
                'waktu_label': peminjaman.dibuat_pada.strftime('%H:%M'),
                'lokasi': peminjaman.barang.lokasi.nama_lokasi if peminjaman.barang.lokasi_id else '-',
                'url': reverse('peminjaman:peminjaman_detail', kwargs={'pk': peminjaman.pk}),
                'badge': 'Diajukan',
                'icon': 'clipboard-list',
                'icon_class': 'bg-amber-50 text-amber-700',
                'is_read': is_read,
            })

        return notifications

    def get_pendaftaran_asleb_notifications(self):
        pengguna = getattr(self.request, 'current_pengguna', None)
        if not pengguna or pengguna.role != 'mahasiswa':
            return []

        pengaturan = PengaturanPendaftaranAsleb.get_solo()

        is_read = bool(
            pengguna.notifikasi_dibaca_pada
            and pengaturan.diperbarui_pada <= pengguna.notifikasi_dibaca_pada
        )
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

        return [{
            'judul': title,
            'deskripsi': description,
            'tanggal': pengaturan.diperbarui_pada.date(),
            'waktu_label': pengaturan.diperbarui_pada.strftime('%H:%M'),
            'lokasi': 'Lab JTIF Usakti',
            'url': url,
            'badge': badge,
            'icon': icon,
            'icon_class': icon_class,
            'is_read': is_read,
        }]

    def get_pendaftaran_asleb_acceptance_notifications(self):
        pengguna = getattr(self.request, 'current_pengguna', None)
        if not pengguna or pengguna.role != 'mahasiswa':
            return []

        pendaftaran_list = (
            PendaftaranAsleb.objects.select_related('matkul')
            .filter(nim=pengguna.nim_nik, status='diterima')
            .order_by('-diperbarui_pada')
        )
        notifications = []

        for pendaftaran in pendaftaran_list:
            is_read = bool(
                pengguna.notifikasi_dibaca_pada
                and pendaftaran.diperbarui_pada <= pengguna.notifikasi_dibaca_pada
            )
            notifications.append({
                'judul': 'Pendaftaran aslab Anda diterima',
                'deskripsi': f'Selamat, pengajuan asisten laboratorium untuk {pendaftaran.matkul} sudah diterima. Silakan menunggu arahan berikutnya dari laboratorium.',
                'tanggal': pendaftaran.diperbarui_pada.date(),
                'waktu_label': pendaftaran.diperbarui_pada.strftime('%H:%M'),
                'lokasi': 'Lab JTIF Usakti',
                'url': '',
                'badge': 'Diterima',
                'icon': 'badge-check',
                'icon_class': 'bg-emerald-50 text-emerald-700',
                'is_read': is_read,
            })

        return notifications
