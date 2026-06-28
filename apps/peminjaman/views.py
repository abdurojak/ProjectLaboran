from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.views import PostOnlyDeleteMixin
from apps.inventaris.models import Barang
from .forms import PeminjamanAlatForm
from .models import PeminjamanAlat
from .notifications import send_peminjaman_request_notifications


BORROWER_ROLES = {'mahasiswa', 'asisten_lab'}


class PeminjamanAlatListView(ListView):
    model = PeminjamanAlat
    template_name = 'peminjaman/peminjaman_list.html'
    context_object_name = 'peminjaman_list'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('barang')
        barang = self.request.GET.get('barang', '').strip()
        tanggal_mulai = self.request.GET.get('tanggal_mulai', '').strip()
        tanggal_selesai = self.request.GET.get('tanggal_selesai', '').strip()
        status = self.request.GET.get('status', '').strip()
        milik_saya = self.request.GET.get('milik_saya') == '1'
        pengguna = getattr(self.request, 'current_pengguna', None)

        if barang:
            queryset = queryset.filter(
                Q(barang__nama__icontains=barang) |
                Q(barang__kode_barang__icontains=barang)
            )

        if tanggal_mulai:
            queryset = queryset.filter(tanggal_pinjam__gte=tanggal_mulai)

        if tanggal_selesai:
            queryset = queryset.filter(tanggal_pinjam__lte=tanggal_selesai)

        if status:
            queryset = queryset.filter(status=status)

        if milik_saya and pengguna and pengguna.role in BORROWER_ROLES:
            queryset = queryset.filter(nim=pengguna.nim_nik)

        peminjaman_list = list(queryset)
        for peminjaman in peminjaman_list:
            peminjaman.can_current_pengguna_change = (
                not pengguna
                or pengguna.role not in BORROWER_ROLES
                or (peminjaman.nim == pengguna.nim_nik and peminjaman.status == 'diajukan')
            )

        return peminjaman_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_barang'] = self.request.GET.get('barang', '').strip()
        context['filter_tanggal_mulai'] = self.request.GET.get('tanggal_mulai', '').strip()
        context['filter_tanggal_selesai'] = self.request.GET.get('tanggal_selesai', '').strip()
        context['filter_status'] = self.request.GET.get('status', '').strip()
        context['filter_milik_saya'] = self.request.GET.get('milik_saya') == '1'
        context['status_choices'] = PeminjamanAlat.STATUS_CHOICES
        context['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return context


class PeminjamanAlatDetailView(DetailView):
    model = PeminjamanAlat
    template_name = 'peminjaman/peminjaman_detail.html'
    context_object_name = 'peminjaman'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pengguna = getattr(self.request, 'current_pengguna', None)
        context['can_current_pengguna_change'] = (
            not pengguna
            or pengguna.role not in BORROWER_ROLES
            or (self.object.nim == pengguna.nim_nik and self.object.status == 'diajukan')
        )
        return context


class PeminjamanAlatCreateView(CreateView):
    model = PeminjamanAlat
    form_class = PeminjamanAlatForm
    template_name = 'peminjaman/peminjaman_form.html'
    success_url = reverse_lazy('peminjaman:peminjaman_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['detail_barang_list'] = Barang.objects.select_related('inventaris', 'lokasi')
        context['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return kwargs

    def form_valid(self, form):
        pengguna = getattr(self.request, 'current_pengguna', None)
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

        created_peminjaman = []
        is_borrower = bool(pengguna and pengguna.role in BORROWER_ROLES)

        for barang in selectable_barang:
            peminjaman = PeminjamanAlat.objects.create(
                barang=barang,
                nama_peminjam=pengguna.nama_pengguna if is_borrower else form.cleaned_data['nama_peminjam'],
                nim=pengguna.nim_nik if is_borrower else form.cleaned_data['nim'],
                no_hp=pengguna.no_hp if is_borrower else form.cleaned_data['no_hp'],
                tanggal_pinjam=form.cleaned_data['tanggal_pinjam'],
                tanggal_kembali=form.cleaned_data['tanggal_kembali'],
                status='diajukan' if is_borrower else form.cleaned_data['status'],
                catatan=form.cleaned_data['catatan'],
            )
            created_peminjaman.append(peminjaman)

        for peminjaman in created_peminjaman:
            if peminjaman.status == 'diajukan':
                send_peminjaman_request_notifications(peminjaman)

        return redirect(self.success_url)


class PeminjamanAlatUpdateView(UpdateView):
    model = PeminjamanAlat
    form_class = PeminjamanAlatForm
    template_name = 'peminjaman/peminjaman_form.html'
    success_url = reverse_lazy('peminjaman:peminjaman_list')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        pengguna = getattr(request, 'current_pengguna', None)
        if pengguna and pengguna.role in BORROWER_ROLES and not self.mahasiswa_can_change(pengguna):
            messages.warning(request, 'Anda hanya bisa mengedit pengajuan milik sendiri yang masih berstatus Diajukan.')
            return redirect('peminjaman:peminjaman_list')

        return super().dispatch(request, *args, **kwargs)

    def mahasiswa_can_change(self, pengguna):
        return self.object.nim == pengguna.nim_nik and self.object.status == 'diajukan'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['detail_barang_list'] = Barang.objects.select_related('inventaris', 'lokasi')
        context['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return context


class PeminjamanAlatDeleteView(PostOnlyDeleteMixin, DeleteView):
    model = PeminjamanAlat
    template_name = 'peminjaman/peminjaman_confirm_delete.html'
    context_object_name = 'peminjaman'
    success_url = reverse_lazy('peminjaman:peminjaman_list')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        pengguna = getattr(request, 'current_pengguna', None)
        if pengguna and pengguna.role in BORROWER_ROLES and not self.mahasiswa_can_change(pengguna):
            messages.warning(request, 'Anda hanya bisa menghapus pengajuan milik sendiri yang masih berstatus Diajukan.')
            return redirect('peminjaman:peminjaman_list')

        return super().dispatch(request, *args, **kwargs)

    def mahasiswa_can_change(self, pengguna):
        return self.object.nim == pengguna.nim_nik and self.object.status == 'diajukan'

