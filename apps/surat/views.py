from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from .forms import SuratPengadaanForm
from .models import SuratPengadaan
from .pdf import build_surat_pdf


class LaboranSuratRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role not in {'admin', 'laboran'}:
            messages.error(request, 'Menu surat hanya tersedia untuk admin dan laboran.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)


class SuratListView(LaboranSuratRequiredMixin, ListView):
    model = SuratPengadaan
    template_name = 'surat/surat_list.html'
    context_object_name = 'surat_list'


class SuratCreateView(LaboranSuratRequiredMixin, CreateView):
    model = SuratPengadaan
    form_class = SuratPengadaanForm
    template_name = 'surat/surat_form.html'
    success_url = reverse_lazy('surat:list')

    def form_valid(self, form):
        form.instance.dibuat_oleh = self.request.current_pengguna
        messages.success(self.request, 'Surat pengadaan berhasil dibuat dan siap diunduh.')
        return super().form_valid(form)


class SuratUpdateView(LaboranSuratRequiredMixin, UpdateView):
    model = SuratPengadaan
    form_class = SuratPengadaanForm
    template_name = 'surat/surat_form.html'
    success_url = reverse_lazy('surat:list')

    def form_valid(self, form):
        messages.success(self.request, 'Surat pengadaan berhasil diperbarui.')
        return super().form_valid(form)


def download_surat_pdf(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    if not pengguna or pengguna.role not in {'admin', 'laboran'}:
        return redirect('dashboard:home')
    surat = get_object_or_404(SuratPengadaan, pk=pk)
    response = HttpResponse(build_surat_pdf(surat), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="surat-pengadaan-{surat.pk}.pdf"'
    return response
