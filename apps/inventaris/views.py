from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .models import Barang


class BarangListView(ListView):
    model = Barang
    template_name = 'inventaris/barang_list.html'
    context_object_name = 'barang_list'


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
