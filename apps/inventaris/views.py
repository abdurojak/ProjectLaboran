from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .models import Barang, Lokasi


class BarangListView(ListView):
    model = Barang
    template_name = 'inventaris/barang_list.html'
    context_object_name = 'barang_list'

    def get_queryset(self):
        return super().get_queryset().select_related('lokasi')


class BarangDetailView(DetailView):
    model = Barang
    template_name = 'inventaris/barang_detail.html'
    context_object_name = 'barang'


class BarangCreateView(CreateView):
    model = Barang
    template_name = 'inventaris/barang_form.html'
    fields = ['nama', 'kode_barang', 'jumlah', 'lokasi', 'kondisi', 'keterangan']
    success_url = reverse_lazy('inventaris:barang_list')


class BarangUpdateView(UpdateView):
    model = Barang
    template_name = 'inventaris/barang_form.html'
    fields = ['nama', 'kode_barang', 'jumlah', 'lokasi', 'kondisi', 'keterangan']
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
