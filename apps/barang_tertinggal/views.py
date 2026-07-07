from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.views import PostOnlyDeleteMixin
from apps.core.permissions import can_manage_lab_operations

from .forms import BarangTertinggalForm
from .models import BarangTertinggal


class LaboranBarangTertinggalRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not can_manage_lab_operations(pengguna):
            messages.error(request, 'Barang tertinggal hanya dapat dikelola oleh Laboran.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)


class BarangTertinggalListView(LaboranBarangTertinggalRequiredMixin, ListView):
    model = BarangTertinggal
    template_name = 'barang_tertinggal/list.html'
    context_object_name = 'barang_tertinggal_list'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = BarangTertinggal.STATUS_CHOICES
        return context


class BarangTertinggalDetailView(LaboranBarangTertinggalRequiredMixin, DetailView):
    model = BarangTertinggal
    template_name = 'barang_tertinggal/detail.html'
    context_object_name = 'barang'


class BarangTertinggalCreateView(LaboranBarangTertinggalRequiredMixin, CreateView):
    model = BarangTertinggal
    form_class = BarangTertinggalForm
    template_name = 'barang_tertinggal/form.html'
    success_url = reverse_lazy('barang_tertinggal:list')


class BarangTertinggalUpdateView(LaboranBarangTertinggalRequiredMixin, UpdateView):
    model = BarangTertinggal
    form_class = BarangTertinggalForm
    template_name = 'barang_tertinggal/form.html'
    context_object_name = 'barang'
    success_url = reverse_lazy('barang_tertinggal:list')


class BarangTertinggalDeleteView(LaboranBarangTertinggalRequiredMixin, PostOnlyDeleteMixin, DeleteView):
    model = BarangTertinggal
    template_name = 'barang_tertinggal/confirm_delete.html'
    context_object_name = 'barang'
    success_url = reverse_lazy('barang_tertinggal:list')

