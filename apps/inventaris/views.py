from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.views import PostOnlyDeleteMixin

from .forms import BarangForm, InventarisBarangCreateForm, InventarisBarangUpdateForm
from .models import ACTIVE_PEMINJAMAN_STATUSES, Barang, InventarisBarang, Lokasi


class BarangListView(ListView):
    model = InventarisBarang
    template_name = 'inventaris/barang_list.html'
    context_object_name = 'barang_list'

    def get_queryset(self):
        queryset = super().get_queryset().annotate(
            jumlah_dipinjam_aktif=Coalesce(
                Sum(
                    'detail_barang__peminjaman__jumlah',
                    filter=Q(detail_barang__peminjaman__status__in=ACTIVE_PEMINJAMAN_STATUSES),
                ),
                0,
            ),
        )
        search = self.request.GET.get('q', '').strip()

        if search:
            queryset = queryset.filter(
                Q(nama__icontains=search) |
                Q(kode_inventaris__icontains=search) |
                Q(keterangan__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '').strip()
        return context


class BarangDetailView(DetailView):
    model = Barang
    template_name = 'inventaris/barang_detail.html'
    context_object_name = 'barang'


class DetailBarangCreateView(CreateView):
    model = Barang
    form_class = BarangForm
    template_name = 'inventaris/detail_barang_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.inventaris = get_object_or_404(InventarisBarang, pk=kwargs['inventaris_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.inventaris = self.inventaris
        form.instance.nama = self.inventaris.nama
        form.instance.jumlah = self.inventaris.jumlah
        response = super().form_valid(form)
        self.inventaris.sync_jumlah_from_detail()
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['inventaris'] = self.inventaris
        return context

    def get_success_url(self):
        return reverse('inventaris:inventaris_detail', args=[self.inventaris.pk])


class DetailBarangUpdateView(UpdateView):
    model = Barang
    form_class = BarangForm
    template_name = 'inventaris/detail_barang_form.html'
    context_object_name = 'barang'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['inventaris'] = self.object.inventaris
        return context

    def get_success_url(self):
        return reverse('inventaris:inventaris_detail', args=[self.object.inventaris_id])


class DetailBarangDeleteView(PostOnlyDeleteMixin, DeleteView):
    model = Barang
    template_name = 'inventaris/detail_barang_confirm_delete.html'
    context_object_name = 'barang'

    def form_valid(self, form):
        inventaris = self.object.inventaris
        with transaction.atomic():
            response = super().form_valid(form)
            if inventaris:
                inventaris.sync_jumlah_from_detail()
        return response

    def get_success_url(self):
        return reverse('inventaris:inventaris_detail', args=[self.object.inventaris_id])


class InventarisBarangDetailView(DetailView):
    model = InventarisBarang
    template_name = 'inventaris/inventaris_detail.html'
    context_object_name = 'inventaris'

    def get_queryset(self):
        return super().get_queryset().annotate(
            jumlah_dipinjam_aktif=Coalesce(
                Sum(
                    'detail_barang__peminjaman__jumlah',
                    filter=Q(detail_barang__peminjaman__status__in=ACTIVE_PEMINJAMAN_STATUSES),
                ),
                0,
            ),
        ).prefetch_related('detail_barang__lokasi')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search = self.request.GET.get('q', '').strip()
        kondisi = self.request.GET.get('kondisi', '').strip()
        lokasi = self.request.GET.get('lokasi', '').strip()
        detail_barang = self.object.detail_barang.select_related('lokasi')

        if search:
            detail_barang = detail_barang.filter(
                Q(kode_barang__icontains=search) |
                Q(lokasi__nama_lokasi__icontains=search) |
                Q(lokasi__kode_lokasi__icontains=search) |
                Q(keterangan__icontains=search)
            )

        if kondisi:
            detail_barang = detail_barang.filter(kondisi=kondisi)

        if lokasi:
            detail_barang = detail_barang.filter(lokasi_id=lokasi)

        context['detail_barang_list'] = detail_barang
        context['detail_search_query'] = search
        context['selected_kondisi'] = kondisi
        context['selected_lokasi'] = lokasi
        context['kondisi_choices'] = Barang.KONDISI_CHOICES
        context['lokasi_choices'] = Lokasi.objects.all()
        return context


class BarangCreateView(CreateView):
    model = InventarisBarang
    form_class = InventarisBarangCreateForm
    template_name = 'inventaris/barang_form.html'
    success_url = reverse_lazy('inventaris:barang_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        lokasi = form.cleaned_data['lokasi']

        for _ in range(self.object.jumlah):
            Barang.objects.create(
                inventaris=self.object,
                nama=self.object.nama,
                jumlah=self.object.jumlah,
                lokasi=lokasi,
                kondisi='baik',
            )

        return response


class BarangUpdateView(UpdateView):
    model = InventarisBarang
    form_class = InventarisBarangUpdateForm
    template_name = 'inventaris/barang_form.html'
    success_url = reverse_lazy('inventaris:barang_list')


class BarangDeleteView(PostOnlyDeleteMixin, DeleteView):
    model = InventarisBarang
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


class LokasiDeleteView(PostOnlyDeleteMixin, DeleteView):
    model = Lokasi
    template_name = 'inventaris/lokasi_confirm_delete.html'
    context_object_name = 'lokasi'
    success_url = reverse_lazy('inventaris:lokasi_list')
