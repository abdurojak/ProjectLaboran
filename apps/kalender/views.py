from datetime import datetime, timedelta

from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import KegiatanKalenderForm
from .models import KegiatanKalender


class KegiatanKalenderListView(ListView):
    model = KegiatanKalender
    template_name = 'kalender/kegiatan_list.html'
    context_object_name = 'kegiatan_list'

    def get_queryset(self):
        return KegiatanKalender.objects.all().order_by('tanggal', 'waktu_mulai')

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

        context['calendar_events'] = calendar_events
        context['upcoming_kegiatan'] = context['kegiatan_list'][:5]
        return context


class KegiatanKalenderDetailView(DetailView):
    model = KegiatanKalender
    template_name = 'kalender/kegiatan_detail.html'
    context_object_name = 'kegiatan'


class KegiatanKalenderCreateView(CreateView):
    model = KegiatanKalender
    form_class = KegiatanKalenderForm
    template_name = 'kalender/kegiatan_form.html'
    success_url = reverse_lazy('kalender:kegiatan_list')


class KegiatanKalenderUpdateView(UpdateView):
    model = KegiatanKalender
    form_class = KegiatanKalenderForm
    template_name = 'kalender/kegiatan_form.html'
    success_url = reverse_lazy('kalender:kegiatan_list')


class KegiatanKalenderDeleteView(DeleteView):
    model = KegiatanKalender
    template_name = 'kalender/kegiatan_confirm_delete.html'
    context_object_name = 'kegiatan'
    success_url = reverse_lazy('kalender:kegiatan_list')


class NotifikasiListView(ListView):
    model = KegiatanKalender
    template_name = 'kalender/notifikasi_list.html'
    context_object_name = 'notifikasi_list'

    def get_queryset(self):
        today = timezone.localdate()
        limit_date = today + timedelta(days=7)
        return (
            KegiatanKalender.objects.filter(
                tampilkan_notifikasi=True,
                tanggal__gte=today,
                tanggal__lte=limit_date,
            )
            .order_by('tanggal', 'waktu_mulai')
        )
