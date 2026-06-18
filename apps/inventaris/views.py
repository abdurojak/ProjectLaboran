from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import BarangForm
from .models import Barang, Lokasi


class BarangListView(ListView):
    model = Barang
    template_name = 'inventaris/barang_list.html'
    context_object_name = 'barang_list'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('lokasi')
        search = self.request.GET.get('q', '').strip()
        kondisi = self.request.GET.get('kondisi', '').strip()
        lokasi = self.request.GET.get('lokasi', '').strip()

        if search:
            queryset = queryset.filter(
                Q(nama__icontains=search) |
                Q(kode_barang__icontains=search) |
                Q(keterangan__icontains=search)
            )

        if kondisi:
            queryset = queryset.filter(kondisi=kondisi)

        if lokasi:
            queryset = queryset.filter(lokasi_id=lokasi)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_kondisi'] = self.request.GET.get('kondisi', '').strip()
        context['selected_lokasi'] = self.request.GET.get('lokasi', '').strip()
        context['kondisi_choices'] = Barang.KONDISI_CHOICES
        context['lokasi_choices'] = Lokasi.objects.all()
        return context


class BarangDetailView(DetailView):
    model = Barang
    template_name = 'inventaris/barang_detail.html'
    context_object_name = 'barang'


class BarangCreateView(CreateView):
    model = Barang
    form_class = BarangForm
    template_name = 'inventaris/barang_form.html'
    success_url = reverse_lazy('inventaris:barang_list')


class BarangUpdateView(UpdateView):
    model = Barang
    form_class = BarangForm
    template_name = 'inventaris/barang_form.html'
    success_url = reverse_lazy('inventaris:barang_list')


class BarangDeleteView(DeleteView):
    model = Barang
    template_name = 'inventaris/barang_confirm_delete.html'
    context_object_name = 'barang'
    success_url = reverse_lazy('inventaris:barang_list')


class LokasiListView(ListView):
    model = Lokasi
    template_name = 'inventaris/lokasi_list.html'
    context_object_name = 'lokasi_list'


class LokasiDetailView(DetailView):
    model = Lokasi
    template_name = 'inventaris/lokasi_detail.html'
    context_object_name = 'lokasi'


class LokasiCreateView(CreateView):
    model = Lokasi
    template_name = 'inventaris/lokasi_form.html'
    fields = ['nama_lokasi', 'ukuran_lokasi']
    success_url = reverse_lazy('inventaris:lokasi_list')


class LokasiUpdateView(UpdateView):
    model = Lokasi
    template_name = 'inventaris/lokasi_form.html'
    fields = ['nama_lokasi', 'ukuran_lokasi']
    success_url = reverse_lazy('inventaris:lokasi_list')


class LokasiDeleteView(DeleteView):
    model = Lokasi
    template_name = 'inventaris/lokasi_confirm_delete.html'
    context_object_name = 'lokasi'
    success_url = reverse_lazy('inventaris:lokasi_list')
