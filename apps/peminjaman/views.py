from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.views import PostOnlyDeleteMixin
from apps.inventaris.models import ACTIVE_PEMINJAMAN_STATUSES, Barang, PaketBarang
from .forms import PeminjamanAlatForm
from .models import PeminjamanAlat, PeminjamanTransaksi
from .notifications import send_peminjaman_request_notifications, send_peminjaman_status_notification


BORROWER_ROLES = {'mahasiswa', 'asisten_lab'}
MANAGER_ROLES = {'admin', 'laboran'}
BULK_STATUS_CHOICES = {'dipinjam', 'dikembalikan', 'hilang', 'rusak', 'digantikan'}
ARCHIVED_STATUS_CHOICES = {'ditolak', 'digantikan', 'dikembalikan'}


def scope_peminjaman_for_pengguna(queryset, pengguna):
    if not pengguna:
        return queryset.none()
    if pengguna.role in MANAGER_ROLES:
        return queryset
    if pengguna.role in BORROWER_ROLES:
        return queryset.filter(nim=pengguna.nim_nik)
    return queryset.none()


def _get_peminjaman_group(peminjaman, for_update=False):
    queryset = PeminjamanAlat.objects.all()
    if for_update:
        queryset = queryset.select_for_update()
    if peminjaman.transaksi_id:
        return queryset.filter(transaksi_id=peminjaman.transaksi_id)
    return queryset.filter(pk=peminjaman.pk)


def _get_peminjaman_group_for_update(peminjaman):
    return _get_peminjaman_group(peminjaman, for_update=True)


@require_GET
def barang_options(request):
    keyword = request.GET.get('q', '').strip()
    active_loans = PeminjamanAlat.objects.filter(
        barang_id=OuterRef('pk'),
        status__in=ACTIVE_PEMINJAMAN_STATUSES,
    )
    queryset = (
        Barang.objects.select_related('inventaris', 'lokasi')
        .annotate(is_borrowed=Exists(active_loans))
        .order_by('kode_barang')
    )
    if keyword:
        queryset = queryset.filter(
            Q(kode_barang__icontains=keyword)
            | Q(nama__icontains=keyword)
            | Q(inventaris__nama__icontains=keyword)
            | Q(lokasi__nama_lokasi__icontains=keyword)
        )

    group_cache = {}

    def get_group_key(barang):
        return f'inventaris-{barang.inventaris_id}' if barang.inventaris_id else f'nama-{slugify(barang.nama)}'

    def get_available_items_for_group(barang):
        group_key = get_group_key(barang)
        if group_key in group_cache:
            return group_cache[group_key]

        group_queryset = Barang.objects.select_related('inventaris').annotate(
            is_borrowed=Exists(active_loans),
        ).exclude(kondisi='rusak_berat').filter(is_borrowed=False)
        if barang.inventaris_id:
            group_queryset = group_queryset.filter(inventaris_id=barang.inventaris_id)
        else:
            group_queryset = group_queryset.filter(inventaris__isnull=True, nama=barang.nama)

        group_cache[group_key] = [
            {
                'id': item.pk,
                'label': f'{item.kode_barang} - {item.nama}',
            }
            for item in group_queryset.order_by('kode_barang')
        ]
        return group_cache[group_key]

    representatives = []
    seen_groups = set()
    for barang in queryset:
        group_key = get_group_key(barang)
        if group_key in seen_groups:
            continue
        seen_groups.add(group_key)
        representatives.append(barang)

    page_obj = Paginator(representatives, 20).get_page(request.GET.get('page', 1))
    results = []

    for barang in page_obj.object_list:
        photo_url = ''
        if barang.foto:
            photo_url = barang.foto.url
        elif barang.inventaris_id and barang.inventaris.foto:
            photo_url = barang.inventaris.foto.url
        group_available_items = get_available_items_for_group(barang)
        is_selectable = bool(group_available_items)
        results.append({
            'id': barang.pk,
            'kode': barang.kode_barang,
            'nama': barang.nama,
            'group': get_group_key(barang),
            'group_available_count': len(group_available_items),
            'group_available_items': group_available_items,
            'lokasi': barang.lokasi.nama_lokasi if barang.lokasi_id else '-',
            'kondisi': barang.get_kondisi_display(),
            'kondisi_key': barang.kondisi,
            'status': f'{len(group_available_items)} tersedia' if is_selectable else 'Tidak tersedia',
            'disabled': not is_selectable,
            'photo_url': photo_url,
        })

    return JsonResponse({
        'results': results,
        'page': page_obj.number,
        'num_pages': page_obj.paginator.num_pages,
        'has_previous': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
    })


@require_POST
def bulk_update_status(request):
    pengguna = getattr(request, 'current_pengguna', None)
    if not pengguna or pengguna.role not in MANAGER_ROLES:
        messages.warning(request, 'Anda tidak memiliki akses untuk mengubah status peminjaman.')
        return redirect('peminjaman:peminjaman_list')

    status = request.POST.get('status', '').strip()
    transaksi_ids = [
        value for value in request.POST.getlist('transaksi_ids')
        if value.isdigit()
    ]
    if not transaksi_ids:
        messages.error(request, 'Pilih minimal satu peminjaman terlebih dahulu.')
        return redirect('peminjaman:peminjaman_list')
    if status not in BULK_STATUS_CHOICES:
        messages.error(request, 'Pilih status peminjaman yang valid.')
        return redirect('peminjaman:peminjaman_list')

    updated_count = 0
    with transaction.atomic():
        detail_list = list(
            PeminjamanAlat.objects.select_for_update()
            .select_related('transaksi')
            .filter(transaksi_id__in=transaksi_ids)
        )
        for peminjaman in detail_list:
            peminjaman.status = status
            peminjaman.save(update_fields=['status', 'diperbarui_pada'])
            send_peminjaman_status_notification(peminjaman)
            updated_count += 1

    messages.success(request, f'{updated_count} detail peminjaman berhasil diperbarui.')
    return redirect('peminjaman:peminjaman_list')


@require_POST
def update_detail_status(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    if not pengguna or pengguna.role not in MANAGER_ROLES:
        messages.warning(request, 'Anda tidak memiliki akses untuk mengubah status peminjaman.')
        return redirect('peminjaman:peminjaman_list')

    status = request.POST.get('status', '').strip()
    detail_ids = [
        value for value in request.POST.getlist('detail_ids')
        if value.isdigit()
    ]
    if not detail_ids:
        messages.error(request, 'Pilih minimal satu detail barang terlebih dahulu.')
        return redirect('peminjaman:peminjaman_detail', pk=pk)
    if status not in BULK_STATUS_CHOICES:
        messages.error(request, 'Pilih status peminjaman yang valid.')
        return redirect('peminjaman:peminjaman_detail', pk=pk)

    updated_count = 0
    with transaction.atomic():
        anchor = get_object_or_404(PeminjamanAlat.objects.select_for_update(), pk=pk)
        detail_queryset = _get_peminjaman_group_for_update(anchor).filter(pk__in=detail_ids)
        for peminjaman in detail_queryset:
            peminjaman.status = status
            peminjaman.save(update_fields=['status', 'diperbarui_pada'])
            send_peminjaman_status_notification(peminjaman)
            updated_count += 1

    messages.success(request, f'{updated_count} detail peminjaman berhasil diperbarui.')
    return redirect('peminjaman:peminjaman_detail', pk=pk)


class PeminjamanAlatListView(ListView):
    model = PeminjamanAlat
    template_name = 'peminjaman/peminjaman_list.html'
    context_object_name = 'peminjaman_list'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('barang', 'paket')
        barang = self.request.GET.get('barang', '').strip()
        tanggal_mulai = self.request.GET.get('tanggal_mulai', '').strip()
        tanggal_selesai = self.request.GET.get('tanggal_selesai', '').strip()
        status = self.request.GET.get('status', '').strip()
        tampilkan_semua = self.request.GET.get('semua') == '1'
        pengguna = getattr(self.request, 'current_pengguna', None)
        queryset = scope_peminjaman_for_pengguna(queryset, pengguna)

        if barang:
            queryset = queryset.filter(
                Q(barang__nama__icontains=barang) |
                Q(barang__kode_barang__icontains=barang)
            )

        parsed_tanggal_mulai = parse_date(tanggal_mulai)
        if parsed_tanggal_mulai:
            queryset = queryset.filter(tanggal_pinjam__gte=parsed_tanggal_mulai)

        parsed_tanggal_selesai = parse_date(tanggal_selesai)
        if parsed_tanggal_selesai:
            queryset = queryset.filter(tanggal_pinjam__lte=parsed_tanggal_selesai)

        if status:
            queryset = queryset.filter(status=status)

        if not tampilkan_semua:
            queryset = queryset.exclude(status__in=ARCHIVED_STATUS_CHOICES)

        if pengguna and pengguna.role in MANAGER_ROLES:
            transaksi_ids = list(
                queryset.exclude(transaksi__isnull=True)
                .values_list('transaksi_id', flat=True)
                .distinct()
            )
            transaksi_list = list(
                PeminjamanTransaksi.objects.filter(pk__in=transaksi_ids)
                .prefetch_related('detail__barang')
                .order_by('-tanggal_pinjam', '-dibuat_pada')
            )
            for transaksi in transaksi_list:
                detail_list = list(transaksi.detail.all())
                transaksi.first_detail = detail_list[0] if detail_list else None
                transaksi.jumlah_barang = len(detail_list)
                transaksi.status_set = sorted({detail.status for detail in detail_list})
                transaksi.status = transaksi.status_set[0] if len(transaksi.status_set) == 1 else 'campuran'
                transaksi.status_display = (
                    dict(PeminjamanAlat.STATUS_CHOICES).get(transaksi.status, 'Campuran')
                )
                transaksi.can_current_pengguna_edit = (
                    detail_list and all(detail.status == 'diajukan' for detail in detail_list)
                )
                transaksi.can_current_pengguna_delete = (
                    detail_list and all(detail.status == 'diajukan' for detail in detail_list)
                )
            return transaksi_list

        peminjaman_list = list(queryset)
        for peminjaman in peminjaman_list:
            peminjaman.can_current_pengguna_edit = (
                pengguna.role in MANAGER_ROLES
                or (peminjaman.nim == pengguna.nim_nik and peminjaman.status == 'diajukan')
            )
            peminjaman.can_current_pengguna_delete = (
                peminjaman.status == 'diajukan'
                and (
                    pengguna.role in MANAGER_ROLES
                    or peminjaman.nim == pengguna.nim_nik
                )
            )

        return peminjaman_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_barang'] = self.request.GET.get('barang', '').strip()
        context['filter_tanggal_mulai'] = self.request.GET.get('tanggal_mulai', '').strip()
        context['filter_tanggal_selesai'] = self.request.GET.get('tanggal_selesai', '').strip()
        context['filter_status'] = self.request.GET.get('status', '').strip()
        context['filter_semua'] = self.request.GET.get('semua') == '1'
        context['status_choices'] = [
            choice for choice in PeminjamanAlat.STATUS_CHOICES
            if choice[0] != 'ditolak'
        ]
        context['bulk_status_choices'] = [
            choice for choice in PeminjamanAlat.STATUS_CHOICES
            if choice[0] in BULK_STATUS_CHOICES
        ]
        context['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        context['is_borrower'] = bool(
            context['current_pengguna'] and context['current_pengguna'].role in BORROWER_ROLES
        )
        context['is_manager'] = bool(
            context['current_pengguna'] and context['current_pengguna'].role in MANAGER_ROLES
        )
        return context


class PeminjamanAlatDetailView(DetailView):
    model = PeminjamanAlat
    template_name = 'peminjaman/peminjaman_detail.html'
    context_object_name = 'peminjaman'

    def get_queryset(self):
        return super().get_queryset().select_related('barang', 'barang__inventaris', 'barang__lokasi', 'paket')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pengguna = getattr(self.request, 'current_pengguna', None)
        if self.object.transaksi_id:
            context['detail_transaksi'] = list(
                self.object.transaksi.detail.select_related('barang', 'barang__inventaris', 'barang__lokasi')
            )
        else:
            context['detail_transaksi'] = [self.object]
        context['can_edit'] = bool(
            pengguna and (
                pengguna.role in MANAGER_ROLES
                or (self.object.nim == pengguna.nim_nik and self.object.status == 'diajukan')
            )
        )
        context['can_delete'] = bool(
            pengguna
            and self.object.status == 'diajukan'
            and (pengguna.role in MANAGER_ROLES or self.object.nim == pengguna.nim_nik)
        )
        context['is_manager'] = bool(pengguna and pengguna.role in MANAGER_ROLES)
        context['detail_status_choices'] = [
            choice for choice in PeminjamanAlat.STATUS_CHOICES
            if choice[0] in BULK_STATUS_CHOICES
        ]
        return context


class PeminjamanAlatCreateView(CreateView):
    model = PeminjamanAlat
    form_class = PeminjamanAlatForm
    template_name = 'peminjaman/peminjaman_form.html'
    success_url = reverse_lazy('peminjaman:peminjaman_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return kwargs

    def form_valid(self, form):
        pengguna = getattr(self.request, 'current_pengguna', None)
        selected_ids = list(dict.fromkeys(
            item.strip()
            for item in form.cleaned_data.get('selected_barang_ids', '').split(',')
            if item.strip().isdigit()
        ))
        paket = form.cleaned_data.get('paket')
        is_borrower = bool(pengguna and pengguna.role in BORROWER_ROLES)
        created_peminjaman = []

        with transaction.atomic():
            if paket:
                selectable_barang = self.get_selectable_barang_for_paket(paket)
                if selectable_barang is None:
                    form.add_error('paket', 'Stok paket tidak mencukupi untuk item yang dipilih.')
                    return self.form_invalid(form)
            else:
                barang_list = (
                    Barang.objects.select_for_update()
                    .select_related('inventaris', 'lokasi')
                    .filter(pk__in=selected_ids)
                )
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

            transaksi = PeminjamanTransaksi.objects.create(
                nama_peminjam=pengguna.nama_pengguna if is_borrower else form.cleaned_data['nama_peminjam'],
                nim=pengguna.nim_nik if is_borrower else form.cleaned_data['nim'],
                no_hp=pengguna.no_hp if is_borrower else form.cleaned_data['no_hp'],
                tanggal_pinjam=form.cleaned_data['tanggal_pinjam'],
                tanggal_kembali=form.cleaned_data['tanggal_kembali'],
                catatan=form.cleaned_data['catatan'],
            )
            for barang in selectable_barang:
                peminjaman = PeminjamanAlat.objects.create(
                    transaksi=transaksi,
                    barang=barang,
                    kode_pinjam=transaksi.kode_pinjam,
                    nama_peminjam=transaksi.nama_peminjam,
                    nim=transaksi.nim,
                    no_hp=transaksi.no_hp,
                    tanggal_pinjam=transaksi.tanggal_pinjam,
                    tanggal_kembali=transaksi.tanggal_kembali,
                    status='diajukan' if is_borrower else form.cleaned_data['status'],
                    catatan=transaksi.catatan,
                    paket=paket,
                )
                created_peminjaman.append(peminjaman)

        for peminjaman in created_peminjaman:
            if peminjaman.status == 'diajukan':
                send_peminjaman_request_notifications(peminjaman)

        return redirect(self.success_url)

    def get_selectable_barang_for_paket(self, paket):
        paket = (
            PaketBarang.objects.select_for_update()
            .prefetch_related('items__inventaris')
            .get(pk=paket.pk)
        )
        selected_barang = []
        active_loans = PeminjamanAlat.objects.filter(
            barang_id=OuterRef('pk'),
            status__in=ACTIVE_PEMINJAMAN_STATUSES,
        )

        for item in paket.items.all():
            available_barang = list(
                Barang.objects.select_for_update()
                .select_related('inventaris', 'lokasi')
                .annotate(is_borrowed=Exists(active_loans))
                .filter(inventaris=item.inventaris, kondisi__in=['baik', 'rusak_ringan'], is_borrowed=False)
                .order_by('kode_barang')[:item.jumlah]
            )
            if len(available_barang) < item.jumlah:
                return None
            selected_barang.extend(available_barang)

        return selected_barang


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

    def form_valid(self, form):
        with transaction.atomic():
            selected_barang = self.get_selected_barang_for_update(form)
            if selected_barang is None:
                return self.form_invalid(form)
            self.object = form.save(commit=False)
            self.sync_group_metadata()
            self.sync_group_details(selected_barang)
        return redirect(self.success_url)

    def get_selected_barang_ids(self, form):
        selected_ids = list(dict.fromkeys(
            item.strip()
            for item in form.cleaned_data.get('selected_barang_ids', '').split(',')
            if item.strip().isdigit()
        ))
        if selected_ids:
            return selected_ids
        barang = form.cleaned_data.get('barang')
        return [str(barang.pk)] if barang else []

    def get_selected_barang_for_update(self, form):
        selected_ids = self.get_selected_barang_ids(form)
        if not selected_ids:
            form.add_error('barang', 'Pilih minimal satu detail barang.')
            return None

        current_barang_ids = set(
            _get_peminjaman_group(self.object).values_list('barang_id', flat=True)
        )
        active_loans = PeminjamanAlat.objects.filter(
            barang_id=OuterRef('pk'),
            status__in=ACTIVE_PEMINJAMAN_STATUSES,
        ).exclude(barang_id__in=current_barang_ids)
        barang_queryset = (
            Barang.objects.select_for_update()
            .select_related('inventaris', 'lokasi')
            .annotate(is_borrowed=Exists(active_loans))
            .filter(pk__in=selected_ids)
        )
        barang_by_id = {str(barang.pk): barang for barang in barang_queryset}
        selected_barang = []
        for selected_id in selected_ids:
            barang = barang_by_id.get(selected_id)
            if not barang:
                continue
            if barang.kondisi == 'rusak_berat' or barang.is_borrowed:
                form.add_error('barang', f'{barang.kode_barang} tidak tersedia untuk dipinjam.')
                return None
            selected_barang.append(barang)

        if len(selected_barang) != len(selected_ids):
            form.add_error('barang', 'Sebagian detail barang yang dipilih tidak ditemukan.')
            return None
        return selected_barang

    def sync_group_metadata(self):
        common_fields = {
            'nama_peminjam': self.object.nama_peminjam,
            'nim': self.object.nim,
            'no_hp': self.object.no_hp,
            'tanggal_pinjam': self.object.tanggal_pinjam,
            'tanggal_kembali': self.object.tanggal_kembali,
            'catatan': self.object.catatan,
        }
        group = _get_peminjaman_group_for_update(self.object)
        group.update(**common_fields)
        if self.object.transaksi_id:
            PeminjamanTransaksi.objects.filter(pk=self.object.transaksi_id).update(**common_fields)

    def sync_group_details(self, selected_barang):
        group = list(_get_peminjaman_group_for_update(self.object).order_by('pk'))
        if not group:
            return

        selected_barang_ids = {barang.pk for barang in selected_barang}
        by_barang_id = {peminjaman.barang_id: peminjaman for peminjaman in group}
        common_fields = {
            'kode_pinjam': self.object.kode_pinjam,
            'nama_peminjam': self.object.nama_peminjam,
            'nim': self.object.nim,
            'no_hp': self.object.no_hp,
            'tanggal_pinjam': self.object.tanggal_pinjam,
            'tanggal_kembali': self.object.tanggal_kembali,
            'status': self.object.status,
            'catatan': self.object.catatan,
            'paket': self.object.paket,
            'transaksi': self.object.transaksi,
        }

        PeminjamanAlat.objects.filter(pk__in=[
            peminjaman.pk for peminjaman in group
            if peminjaman.barang_id not in selected_barang_ids
        ]).delete()

        for barang in selected_barang:
            peminjaman = by_barang_id.get(barang.pk)
            if peminjaman:
                for field, value in common_fields.items():
                    setattr(peminjaman, field, value)
                peminjaman.barang = barang
                peminjaman.save()
                continue

            PeminjamanAlat.objects.create(
                barang=barang,
                **common_fields,
            )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        kwargs['current_group_barang_ids'] = list(
            _get_peminjaman_group(self.object).values_list('barang_id', flat=True)
        )
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        context['selected_barang_list'] = [
            peminjaman.barang
            for peminjaman in _get_peminjaman_group(self.object).select_related('barang').order_by('barang__kode_barang')
        ]
        return context


class PeminjamanAlatDeleteView(PostOnlyDeleteMixin, DeleteView):
    model = PeminjamanAlat
    template_name = 'peminjaman/peminjaman_confirm_delete.html'
    context_object_name = 'peminjaman'
    success_url = reverse_lazy('peminjaman:peminjaman_list')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        pengguna = getattr(request, 'current_pengguna', None)
        if self.object.status != 'diajukan':
            messages.warning(request, 'Riwayat peminjaman yang sudah diproses tidak dapat dihapus.')
            return redirect('peminjaman:peminjaman_list')
        if pengguna and pengguna.role in BORROWER_ROLES and not self.mahasiswa_can_change(pengguna):
            messages.warning(request, 'Anda hanya bisa menghapus pengajuan milik sendiri yang masih berstatus Diajukan.')
            return redirect('peminjaman:peminjaman_list')

        return super().dispatch(request, *args, **kwargs)

    def mahasiswa_can_change(self, pengguna):
        return self.object.nim == pengguna.nim_nik and self.object.status == 'diajukan'

    def form_valid(self, form):
        transaksi = self.object.transaksi
        pengguna = getattr(self.request, 'current_pengguna', None)
        with transaction.atomic():
            if pengguna and pengguna.role in MANAGER_ROLES:
                _get_peminjaman_group_for_update(self.object).delete()
            else:
                PeminjamanAlat.objects.select_for_update().filter(pk=self.object.pk).delete()
            if transaksi and not transaksi.detail.exists():
                transaksi.delete()
        return redirect(self.success_url)

