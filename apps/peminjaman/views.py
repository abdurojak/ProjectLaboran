from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.inventaris.models import Barang
from .forms import PeminjamanAlatForm
from .models import PeminjamanAlat


class PeminjamanAlatListView(ListView):
    model = PeminjamanAlat
    template_name = 'peminjaman/peminjaman_list.html'
    context_object_name = 'peminjaman_list'


class PeminjamanAlatDetailView(DetailView):
    model = PeminjamanAlat
    template_name = 'peminjaman/peminjaman_detail.html'
    context_object_name = 'peminjaman'


class PeminjamanAlatCreateView(CreateView):
    model = PeminjamanAlat
    form_class = PeminjamanAlatForm
    template_name = 'peminjaman/peminjaman_form.html'
    success_url = reverse_lazy('peminjaman:peminjaman_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['detail_barang_list'] = Barang.objects.select_related('inventaris', 'lokasi')
        return context

    def form_valid(self, form):
        selected_ids = [
            item.strip()
            for item in form.cleaned_data.get('selected_barang_ids', '').split(',')
            if item.strip()
        ]
        barang_list = Barang.objects.select_related('inventaris', 'lokasi').filter(pk__in=selected_ids)
        barang_by_id = {str(barang.pk): barang for barang in barang_list}
        selectable_barang = [
            barang_by_id[item]
            for item in selected_ids
            if (
                item in barang_by_id
                and barang_by_id[item].kondisi != 'rusak_berat'
                and not barang_by_id[item].sedang_dipinjam
            )
        ]

        if not selectable_barang:
            form.add_error('barang', 'Pilih minimal satu detail barang yang tersedia dan tidak rusak berat.')
            return self.form_invalid(form)

        for barang in selectable_barang:
            PeminjamanAlat.objects.create(
                barang=barang,
                nama_peminjam=form.cleaned_data['nama_peminjam'],
                nim=form.cleaned_data['nim'],
                no_hp=form.cleaned_data['no_hp'],
                jumlah=1,
                tanggal_pinjam=form.cleaned_data['tanggal_pinjam'],
                tanggal_kembali=form.cleaned_data['tanggal_kembali'],
                status=form.cleaned_data['status'],
                catatan=form.cleaned_data['catatan'],
            )

        return redirect(self.success_url)


class PeminjamanAlatUpdateView(UpdateView):
    model = PeminjamanAlat
    form_class = PeminjamanAlatForm
    template_name = 'peminjaman/peminjaman_form.html'
    success_url = reverse_lazy('peminjaman:peminjaman_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['detail_barang_list'] = Barang.objects.select_related('inventaris', 'lokasi')
        return context


class PeminjamanAlatDeleteView(DeleteView):
    model = PeminjamanAlat
    template_name = 'peminjaman/peminjaman_confirm_delete.html'
    context_object_name = 'peminjaman'
    success_url = reverse_lazy('peminjaman:peminjaman_list')

