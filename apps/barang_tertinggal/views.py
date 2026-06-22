from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import BarangTertinggalForm
from .models import BarangTertinggal


class BarangTertinggalListView(ListView):
    model = BarangTertinggal
    template_name = 'barang_tertinggal/list.html'
    context_object_name = 'barang_tertinggal_list'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = BarangTertinggal.STATUS_CHOICES
        return context


class BarangTertinggalDetailView(DetailView):
    model = BarangTertinggal
    template_name = 'barang_tertinggal/detail.html'
    context_object_name = 'barang'


class BarangTertinggalCreateView(CreateView):
    model = BarangTertinggal
    form_class = BarangTertinggalForm
    template_name = 'barang_tertinggal/form.html'
    success_url = reverse_lazy('barang_tertinggal:list')


class BarangTertinggalUpdateView(UpdateView):
    model = BarangTertinggal
    form_class = BarangTertinggalForm
    template_name = 'barang_tertinggal/form.html'
    context_object_name = 'barang'
    success_url = reverse_lazy('barang_tertinggal:list')


class BarangTertinggalDeleteView(DeleteView):
    model = BarangTertinggal
    template_name = 'barang_tertinggal/confirm_delete.html'
    context_object_name = 'barang'
    success_url = reverse_lazy('barang_tertinggal:list')

