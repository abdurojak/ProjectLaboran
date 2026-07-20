from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.views import PostOnlyDeleteMixin
from apps.core.permissions import can_manage_lab_operations
from apps.kalender.realtime import send_data_refresh

from .forms import BarangTertinggalForm
from .models import BarangTertinggal
from .notifications import publish_barang_tertinggal_news


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

    def form_valid(self, form):
        response = super().form_valid(form)
        barang_id = self.object.pk
        transaction.on_commit(
            lambda: publish_barang_tertinggal_news(BarangTertinggal.objects.get(pk=barang_id))
        )
        messages.success(self.request, 'Barang tersimpan dan berita telah dikirim ke dashboard Mahasiswa.')
        return response


class BarangTertinggalUpdateView(LaboranBarangTertinggalRequiredMixin, UpdateView):
    model = BarangTertinggal
    form_class = BarangTertinggalForm
    template_name = 'barang_tertinggal/form.html'
    context_object_name = 'barang'
    success_url = reverse_lazy('barang_tertinggal:list')

    def form_valid(self, form):
        response = super().form_valid(form)
        transaction.on_commit(lambda: send_data_refresh(
            ('laboran', 'mahasiswa'), 'lost_item.updated', ['/barang-tertinggal/', '/'],
            related_object_id=self.object.pk, title='Berita barang tertinggal diperbarui',
        ))
        return response


class BarangTertinggalDeleteView(LaboranBarangTertinggalRequiredMixin, PostOnlyDeleteMixin, DeleteView):
    model = BarangTertinggal
    template_name = 'barang_tertinggal/confirm_delete.html'
    context_object_name = 'barang'
    success_url = reverse_lazy('barang_tertinggal:list')

    def form_valid(self, form):
        object_id = self.object.pk
        response = super().form_valid(form)
        transaction.on_commit(lambda: send_data_refresh(
            ('laboran', 'mahasiswa'), 'lost_item.deleted', ['/barang-tertinggal/', '/'],
            related_object_id=object_id, title='Berita barang tertinggal diperbarui',
        ))
        return response


class MahasiswaBarangBeritaRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role != 'mahasiswa':
            messages.error(request, 'Berita barang hilang hanya dapat dibuka oleh Mahasiswa.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)


class BarangTertinggalBeritaListView(MahasiswaBarangBeritaRequiredMixin, ListView):
    model = BarangTertinggal
    template_name = 'barang_tertinggal/berita_list.html'
    context_object_name = 'berita_barang_list'

    def get_queryset(self):
        return BarangTertinggal.objects.exclude(status='diambil').order_by(
            '-tanggal_ditemukan', '-dibuat_pada'
        )


class BarangTertinggalBeritaDetailView(MahasiswaBarangBeritaRequiredMixin, DetailView):
    model = BarangTertinggal
    template_name = 'barang_tertinggal/berita_detail.html'
    context_object_name = 'barang'

    def get_queryset(self):
        return BarangTertinggal.objects.exclude(status='diambil')

