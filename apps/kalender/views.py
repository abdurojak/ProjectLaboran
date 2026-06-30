from datetime import datetime, timedelta

from django.db.models import Q
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.asleb.models import Asleb
from apps.core.views import PostOnlyDeleteMixin
from apps.jadwal.models import JadwalPraktikum

from .forms import KegiatanKalenderForm
from .models import KegiatanKalender, Notifikasi
from .notifications import sync_user_notifications
from .utils import build_manual_notification, get_perayaan_calendar_events, get_perayaan_notifications


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
        jadwal_praktikum_saya = get_asisten_lab_jadwal_queryset(pengguna)
        calendar_events.extend(get_perayaan_calendar_events(timezone.localdate().year))

        context['calendar_events'] = calendar_events
        context['upcoming_kegiatan'] = context['kegiatan_list'][:5]
        context['jadwal_praktikum_saya'] = jadwal_praktikum_saya
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
    model = Notifikasi
    template_name = 'kalender/notifikasi_list.html'
    context_object_name = 'notifikasi_list'
    notifications_per_page = 20
    paginate_by = 20

    def get_queryset(self):
        pengguna = getattr(self.request, 'current_pengguna', None)
        if not pengguna:
            return Notifikasi.objects.none()

        sync_user_notifications(pengguna)
        return Notifikasi.objects.filter(pengguna=pengguna).order_by('-source_updated_at', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notifikasi_list'] = list(context['notifikasi_list'])
        context['page_obj'].object_list = context['notifikasi_list']
        self.mark_notifications_as_read()
        return context

    def mark_notifications_as_read(self):
        pengguna = getattr(self.request, 'current_pengguna', None)
        if not pengguna:
            return

        now = timezone.now()
        Notifikasi.objects.filter(pengguna=pengguna, dibaca_pada__isnull=True).update(dibaca_pada=now)
        pengguna.notifikasi_dibaca_pada = now
        pengguna.save(update_fields=['notifikasi_dibaca_pada', 'diperbarui_pada'])
