from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.core.permissions import LABORAN_ROLE

from .forms import FotoRuanganLabForm
from .models import FotoRuanganLab, GrupRuanganGabungan, RuanganLab


class LaboranRuanganRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role != LABORAN_ROLE:
            messages.warning(request, 'Kelola foto lab hanya tersedia untuk Laboran.')
            return redirect('ruangan:ruangan_list')
        return super().dispatch(request, *args, **kwargs)


class RuanganListView(ListView):
    model = RuanganLab
    template_name = 'ruangan/ruangan_list.html'
    context_object_name = 'ruangan_list'

    def get_queryset(self):
        return RuanganLab.objects.filter(aktif=True).prefetch_related('foto_lab').order_by('nama')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['jumlah_ruangan'] = context['ruangan_list'].count()
        context['grup_gabungan_list'] = (
            GrupRuanganGabungan.objects.filter(aktif=True)
            .prefetch_related('ruangan')
            .order_by('nama')
        )
        return context


class FotoRuanganCreateView(LaboranRuanganRequiredMixin, CreateView):
    model = FotoRuanganLab
    form_class = FotoRuanganLabForm
    template_name = 'ruangan/foto_form.html'
    success_url = reverse_lazy('ruangan:ruangan_list')

    def dispatch(self, request, *args, **kwargs):
        self.ruangan = get_object_or_404(RuanganLab, pk=kwargs['ruangan_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.ruangan = self.ruangan
        messages.success(self.request, 'Foto lab berhasil ditambahkan.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ruangan'] = self.ruangan
        context['form_title'] = 'Tambah Foto Lab'
        return context


class FotoRuanganUpdateView(LaboranRuanganRequiredMixin, UpdateView):
    model = FotoRuanganLab
    form_class = FotoRuanganLabForm
    template_name = 'ruangan/foto_form.html'
    success_url = reverse_lazy('ruangan:ruangan_list')

    def form_valid(self, form):
        messages.success(self.request, 'Foto lab berhasil diperbarui.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ruangan'] = self.object.ruangan
        context['form_title'] = 'Edit Foto Lab'
        return context


class FotoRuanganDeleteView(LaboranRuanganRequiredMixin, DeleteView):
    model = FotoRuanganLab
    template_name = 'ruangan/foto_confirm_delete.html'
    success_url = reverse_lazy('ruangan:ruangan_list')

    def form_valid(self, form):
        messages.success(self.request, 'Foto lab berhasil dihapus.')
        return super().form_valid(form)
