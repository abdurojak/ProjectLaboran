import logging
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from html import escape

from django.contrib import messages
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.text import slugify
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from apps.core.views import PostOnlyDeleteMixin
from apps.core.permissions import ASISTEN_LAB_ROLE, LABORAN_ROLE, can_manage_lab_operations
from apps.jadwal.models import JadwalPraktikum
from apps.kalender.realtime import send_attendance_update, send_honor_update
from apps.pengguna.models import Pengguna
from apps.pendaftaran_asleb.forms import PengaturanBiayaTransferForm
from apps.pendaftaran_asleb.models import PengaturanBiayaTransfer

from .forms import (
    AbsensiAslebForm,
    AslebForm,
    ENABLE_CAMERA_LOCATION_CAPTURE,
    HonorAslebForm,
    KonfirmasiTransferHonorForm,
    HasilPraktikumMahasiswaForm,
    ModulPraktikumForm,
    PesertaPraktikumBulkForm,
    PesertaPraktikumForm,
    SuratHonorAslebGenerateForm,
    get_asleb_matkul,
)
from .models import (
    AbsensiAsleb,
    Asleb,
    HasilPraktikumMahasiswa,
    HonorAsleb,
    ModulPraktikum,
    PengaturanAbsensiAsleb,
    PesertaPraktikum,
    SuratHonorAsleb,
)
from .surat_honor import generate_surat_honor_pdf, month_year_label


logger = logging.getLogger(__name__)


class HonorAdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not can_manage_lab_operations(pengguna):
            messages.error(request, 'Hanya laboran yang bisa mengelola rekap honorarium.')
            return redirect('asleb:honor_list')
        return super().dispatch(request, *args, **kwargs)


class LabOperationsRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not can_manage_lab_operations(pengguna):
            messages.error(request, 'Menu ini hanya tersedia untuk Laboran.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)


class HonorAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role not in {LABORAN_ROLE, ASISTEN_LAB_ROLE}:
            messages.error(request, 'Anda tidak memiliki akses ke rekap honorarium.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)


class AslebListView(LabOperationsRequiredMixin, ListView):
    model = Asleb
    template_name = 'asleb/asleb_list.html'
    context_object_name = 'asleb_list'

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').strip()

        if search:
            queryset = queryset.filter(
                Q(nama__icontains=search) |
                Q(nim__icontains=search) |
                Q(no_hp__icontains=search) |
                Q(program_studi__icontains=search) |
                Q(matkul__icontains=search)
            )

        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_status'] = self.request.GET.get('status', '').strip()
        context['status_choices'] = Asleb.STATUS_CHOICES
        pengguna = getattr(self.request, 'current_pengguna', None)
        context['can_end_asleb'] = can_manage_lab_operations(pengguna)
        return context


@require_POST
@transaction.atomic
def end_asleb_membership(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    if not can_manage_lab_operations(pengguna):
        messages.error(request, 'Hanya laboran yang dapat mengakhiri masa tugas aslab.')
        return redirect('asleb:asleb_list')

    asleb = get_object_or_404(Asleb, pk=pk)
    Asleb.objects.filter(nim=asleb.nim, status='aktif').update(status='nonaktif')
    akun = Pengguna.objects.filter(nim_nik=asleb.nim).first()
    if akun and akun.role == 'asisten_lab':
        akun.role = 'mahasiswa'
        akun.save(update_fields=['role', 'diperbarui_pada'])

    messages.success(request, f'Masa tugas {asleb.nama} diakhiri. Role akun kini menjadi Mahasiswa.')
    return redirect('asleb:asleb_list')


class AslebDetailView(LabOperationsRequiredMixin, DetailView):
    model = Asleb
    template_name = 'asleb/asleb_detail.html'
    context_object_name = 'asleb'


class AslebCreateView(LabOperationsRequiredMixin, CreateView):
    model = Asleb
    form_class = AslebForm
    template_name = 'asleb/asleb_form.html'
    success_url = reverse_lazy('asleb:asleb_list')


class AslebUpdateView(LabOperationsRequiredMixin, UpdateView):
    model = Asleb
    form_class = AslebForm
    template_name = 'asleb/asleb_form.html'
    success_url = reverse_lazy('asleb:asleb_list')


class AslebDeleteView(LabOperationsRequiredMixin, PostOnlyDeleteMixin, DeleteView):
    model = Asleb
    template_name = 'asleb/asleb_confirm_delete.html'
    context_object_name = 'asleb'
    success_url = reverse_lazy('asleb:asleb_list')


class HonorAslebListView(HonorAccessMixin, ListView):
    model = HonorAsleb
    template_name = 'asleb/honor_list.html'
    context_object_name = 'honor_list'

    def get_queryset(self):
        queryset = HonorAsleb.objects.select_related('asleb', 'assigned_laboran')
        pengguna = getattr(self.request, 'current_pengguna', None)
        search = self.request.GET.get('q', '').strip()
        bulan = self.request.GET.get('bulan', '').strip()
        status = self.request.GET.get('status', '').strip()

        if pengguna and pengguna.role == LABORAN_ROLE:
            queryset = queryset.filter(assigned_laboran=pengguna)
        elif pengguna and pengguna.role == ASISTEN_LAB_ROLE:
            queryset = queryset.filter(asleb__nim=pengguna.nim_nik)
        elif pengguna:
            queryset = queryset.none()

        if search:
            queryset = queryset.filter(
                Q(asleb__nama__icontains=search) |
                Q(asleb__nim__icontains=search) |
                Q(asleb__matkul__icontains=search) |
                Q(pic_transfer__icontains=search) |
                Q(assigned_laboran__nama_pengguna__icontains=search)
            )

        if bulan:
            try:
                year, month = bulan.split('-')
                queryset = queryset.filter(bulan__month=month, bulan__year=year)
            except ValueError:
                messages.error(self.request, 'Format bulan tidak valid.')
                queryset = queryset.none()

        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bulan_ini = timezone.localdate().replace(day=1)
        selected_bulan = self.request.GET.get('bulan', bulan_ini.strftime('%Y-%m'))
        total_honor = self.get_queryset().aggregate(total=Sum('jumlah'))['total'] or 0
        pengguna = getattr(self.request, 'current_pengguna', None)
        base_honor_qs = HonorAsleb.objects.all()
        if pengguna and pengguna.role == LABORAN_ROLE:
            base_honor_qs = base_honor_qs.filter(assigned_laboran=pengguna)
        elif pengguna and pengguna.role == ASISTEN_LAB_ROLE:
            base_honor_qs = base_honor_qs.filter(asleb__nim=pengguna.nim_nik)
        elif pengguna:
            base_honor_qs = base_honor_qs.none()

        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_bulan'] = selected_bulan
        context['selected_status'] = self.request.GET.get('status', '').strip()
        context['status_choices'] = HonorAsleb.STATUS_CHOICES
        context['total_honor'] = f'Rp {total_honor:,.0f}'.replace(',', '.')
        context['laboran_count'] = Pengguna.objects.filter(role='laboran', is_verified=True).count()
        context['unassigned_honor_count'] = base_honor_qs.filter(assigned_laboran__isnull=True).count()
        context['is_admin'] = False
        context['is_laboran'] = bool(pengguna and pengguna.role == LABORAN_ROLE)
        context['is_asisten_lab'] = bool(pengguna and pengguna.role == ASISTEN_LAB_ROLE)
        context['formula_note'] = 'Total Honor = min(7 x Total Pertemuan, 60) x Honor/Jam. Level otomatis: periode aslab ke-1 dan ke-2 Junior Rp7.000, mulai ke-3 Senior Rp8.000.'
        context['biaya_transfer_form'] = PengaturanBiayaTransferForm(instance=PengaturanBiayaTransfer.get_solo())
        return context


@require_POST
def update_transfer_fees(request):
    pengguna = getattr(request, 'current_pengguna', None)
    if not can_manage_lab_operations(pengguna):
        messages.error(request, 'Hanya laboran yang dapat mengubah biaya transfer.')
        return redirect('asleb:honor_list')
    form = PengaturanBiayaTransferForm(request.POST, instance=PengaturanBiayaTransfer.get_solo())
    if form.is_valid():
        form.save()
        for honor in HonorAsleb.objects.exclude(status='dibayar'):
            honor.save()
        messages.success(request, 'Biaya admin transfer berhasil diperbarui.')
    else:
        messages.error(request, 'Biaya admin tidak valid. Gunakan angka nol atau lebih besar.')
    return redirect('asleb:honor_list')


class HonorAslebCreateView(HonorAdminRequiredMixin, CreateView):
    model = HonorAsleb
    form_class = HonorAslebForm
    template_name = 'asleb/honor_form.html'
    success_url = reverse_lazy('asleb:honor_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        transaction.on_commit(lambda: send_honor_update(self.object, event='honor.created'))
        return response


class HonorAslebUpdateView(UpdateView):
    model = HonorAsleb
    form_class = HonorAslebForm
    template_name = 'asleb/honor_form.html'
    success_url = reverse_lazy('asleb:honor_list')

    def get_queryset(self):
        queryset = super().get_queryset()
        pengguna = getattr(self.request, 'current_pengguna', None)
        if pengguna and pengguna.role == LABORAN_ROLE:
            return queryset.filter(assigned_laboran=pengguna)
        if pengguna and pengguna.role != LABORAN_ROLE:
            return queryset.none()
        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        transaction.on_commit(lambda: send_honor_update(self.object, event='honor.updated'))
        return response


class HonorAslebDeleteView(HonorAdminRequiredMixin, PostOnlyDeleteMixin, DeleteView):
    model = HonorAsleb
    template_name = 'asleb/honor_confirm_delete.html'
    context_object_name = 'honor'
    success_url = reverse_lazy('asleb:honor_list')


class SuratHonorAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        cleanup_expired_surat_honor()
        pengguna = getattr(request, 'current_pengguna', None)
        if not can_manage_lab_operations(pengguna):
            messages.error(request, 'Hanya laboran yang bisa mengakses arsip surat honor.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)


class SuratHonorAslebListView(SuratHonorAccessMixin, ListView):
    model = SuratHonorAsleb
    template_name = 'asleb/surat_honor_list.html'
    context_object_name = 'surat_list'

    def get_queryset(self):
        queryset = SuratHonorAsleb.objects.select_related('dibuat_oleh')
        search = self.request.GET.get('q', '').strip()
        bulan = self.request.GET.get('bulan', '').strip()

        if search:
            queryset = queryset.filter(
                Q(nomor_surat__icontains=search) |
                Q(perihal__icontains=search) |
                Q(dibuat_oleh__nama_pengguna__icontains=search)
            )

        if bulan:
            queryset = queryset.filter(bulan__year=bulan.split('-')[0], bulan__month=bulan.split('-')[1])

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_bulan'] = self.request.GET.get('bulan', timezone.localdate().replace(day=1).strftime('%Y-%m'))
        return context


class SuratHonorAslebGenerateView(SuratHonorAccessMixin, FormView):
    form_class = SuratHonorAslebGenerateForm
    template_name = 'asleb/surat_honor_generate.html'
    success_url = reverse_lazy('asleb:surat_honor_list')

    def get_initial(self):
        today = timezone.localdate()
        bulan = today.replace(day=1)
        return {
            'bulan': bulan.strftime('%Y-%m'),
            'tanggal_surat': today,
            'nomor_surat': f'0001/AK.01.02/FTI-Kajur.TIF/{roman_month(today.month)}/{today.year}',
            'perihal': SuratHonorAsleb._meta.get_field('perihal').default,
        }

    def form_valid(self, form):
        pengguna = getattr(self.request, 'current_pengguna', None)
        bulan = form.cleaned_data['bulan']
        honors = list(HonorAsleb.objects.select_related('asleb').filter(
            bulan__year=bulan.year,
            bulan__month=bulan.month,
        ).order_by('asleb__matkul', 'asleb__nama'))

        if not honors:
            form.add_error('bulan', 'Belum ada rekap honor aslab untuk bulan ini.')
            return self.form_invalid(form)

        total_honor = sum(honor.jumlah for honor in honors)
        pdf_bytes = generate_surat_honor_pdf(
            honors=honors,
            nomor_surat=form.cleaned_data['nomor_surat'],
            tanggal_surat=form.cleaned_data['tanggal_surat'],
            bulan=bulan,
            perihal=form.cleaned_data['perihal'],
        )
        filename = f"surat-honor-aslab-{slugify(month_year_label(bulan))}-{timezone.now():%Y%m%d%H%M%S}.pdf"
        surat = SuratHonorAsleb(
            bulan=bulan,
            nomor_surat=form.cleaned_data['nomor_surat'],
            tanggal_surat=form.cleaned_data['tanggal_surat'],
            perihal=form.cleaned_data['perihal'],
            dibuat_oleh=pengguna,
            total_honor=total_honor,
            jumlah_asleb=len(honors),
        )
        surat.file_pdf.save(filename, ContentFile(pdf_bytes), save=True)
        messages.success(self.request, f'Surat honor {surat.bulan_label} berhasil digenerate dan disimpan ke arsip.')
        return super().form_valid(form)


def download_surat_honor(request, pk):
    cleanup_expired_surat_honor()
    pengguna = getattr(request, 'current_pengguna', None)
    if not can_manage_lab_operations(pengguna):
        messages.error(request, 'Hanya laboran yang bisa mengunduh surat honor.')
        return redirect('dashboard:home')

    surat = get_object_or_404(SuratHonorAsleb, pk=pk)
    return FileResponse(
        surat.file_pdf.open('rb'),
        as_attachment=True,
        filename=f'surat-honor-aslab-{slugify(surat.bulan_label)}.pdf',
        content_type='application/pdf',
    )


class AbsensiAslebListView(ListView):
    model = AbsensiAsleb
    template_name = 'asleb/absensi_list.html'
    context_object_name = 'absensi_list'

    def get_queryset(self):
        queryset = AbsensiAsleb.objects.select_related('asleb')
        pengguna = getattr(self.request, 'current_pengguna', None)
        search = self.request.GET.get('q', '').strip()
        modul = self.request.GET.get('modul', '').strip()

        if pengguna and pengguna.role == ASISTEN_LAB_ROLE:
            queryset = queryset.filter(asleb__nim=pengguna.nim_nik)
        elif pengguna and pengguna.role != LABORAN_ROLE:
            queryset = queryset.none()

        if search:
            queryset = queryset.filter(
                Q(asleb__nama__icontains=search) |
                Q(asleb__nim__icontains=search) |
                Q(materi_praktikum__icontains=search) |
                Q(pekerjaan__icontains=search)
            )

        if modul:
            queryset = queryset.filter(modul=modul)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pengguna = getattr(self.request, 'current_pengguna', None)
        context['pengaturan_absensi'] = PengaturanAbsensiAsleb.get_solo()
        context['is_asisten_lab'] = bool(pengguna and pengguna.role == ASISTEN_LAB_ROLE)
        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_modul'] = self.request.GET.get('modul', '').strip()
        context['modul_choices'] = AbsensiAsleb.MODUL_CHOICES
        context['asleb_profile'] = self.get_asleb_profile(pengguna) if pengguna else None
        context['jadwal_aktif'] = (
            get_active_absensi_schedule(context['asleb_profile'])
            if context['asleb_profile'] and context['pengaturan_absensi'].dibuka
            else None
        )
        context['modul_list'] = self.get_modul_list(pengguna, context['asleb_profile'])
        context['can_manage_modul'] = can_manage_lab_operations(pengguna)
        return context

    def get_modul_list(self, pengguna, asleb_profile):
        queryset = ModulPraktikum.objects.select_related('matkul', 'diunggah_oleh')
        if pengguna and pengguna.role == ASISTEN_LAB_ROLE:
            matkul = get_asleb_matkul(asleb_profile) if asleb_profile else None
            return queryset.filter(matkul=matkul) if matkul else queryset.none()
        return queryset

    def get_asleb_profile(self, pengguna):
        if not pengguna or pengguna.role != ASISTEN_LAB_ROLE:
            return None

        return Asleb.objects.filter(nim=pengguna.nim_nik).first()


class AbsensiAslebCreateView(CreateView):
    model = AbsensiAsleb
    form_class = AbsensiAslebForm
    template_name = 'asleb/absensi_form.html'
    success_url = reverse_lazy('asleb:absensi_list')

    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        self.asleb = Asleb.objects.filter(nim=getattr(pengguna, 'nim_nik', '')).first()

        if not pengguna or pengguna.role != ASISTEN_LAB_ROLE:
            messages.error(request, 'Absensi hanya bisa diisi oleh role Asisten Lab.')
            return redirect('dashboard:home')

        if not self.asleb:
            messages.error(request, 'Data Aslab untuk akun ini belum ditemukan.')
            return redirect('dashboard:home')

        if not PengaturanAbsensiAsleb.get_solo().dibuka:
            messages.warning(request, 'Absensi aslab sedang ditutup oleh laboran.')
            return redirect('asleb:absensi_list')

        self.jadwal = get_active_absensi_schedule(self.asleb)
        if not self.jadwal:
            messages.warning(request, 'Absensi hanya dapat diisi saat jadwal praktikum sedang berlangsung.')
            return redirect('asleb:absensi_list')

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['files'] = self.request.FILES or None
        kwargs['asleb'] = self.asleb
        kwargs['jadwal'] = self.jadwal
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['enable_camera_location_capture'] = ENABLE_CAMERA_LOCATION_CAPTURE
        return context

    def form_valid(self, form):
        form.instance.asleb = self.asleb
        response = super().form_valid(form)
        sync_honor_from_absensi(self.object)
        transaction.on_commit(lambda: send_attendance_update(self.object))
        messages.success(self.request, f'Absensi Modul {self.object.modul} berhasil disimpan.')
        return response

    def form_invalid(self, form):
        error_messages = []
        for field_name, errors in form.errors.items():
            label = 'Form'
            if field_name != '__all__':
                label = form.fields.get(field_name).label if form.fields.get(field_name) else field_name
            for error in errors:
                error_messages.append(f'{label}: {error}')

        if error_messages:
            messages.error(self.request, 'Absensi belum bisa disimpan: ' + ' | '.join(error_messages))

        logger.warning(
            'Absensi form invalid for nim=%s errors=%s post=%s files=%s',
            getattr(self.asleb, 'nim', ''),
            form.errors.get_json_data(),
            {
                key: value
                for key, value in self.request.POST.items()
                if key not in {'csrfmiddlewaretoken'}
            },
            {
                key: {
                    'name': uploaded_file.name,
                    'content_type': getattr(uploaded_file, 'content_type', ''),
                    'size': getattr(uploaded_file, 'size', 0),
                }
                for key, uploaded_file in self.request.FILES.items()
            },
        )
        return super().form_invalid(form)


def get_active_absensi_schedule(asleb, current_time=None):
    current_time = current_time or timezone.localtime()
    matkul = get_asleb_matkul(asleb)
    if not matkul:
        return None
    day_keys = [key for key, _ in JadwalPraktikum.HARI_CHOICES]
    weekday = current_time.weekday()
    if weekday >= len(day_keys):
        return None
    current_clock = current_time.time().replace(tzinfo=None)
    return JadwalPraktikum.objects.filter(
        mata_kuliah=str(matkul),
        hari=day_keys[weekday],
        status=JadwalPraktikum.STATUS_DITERIMA,
        waktu_mulai__lte=current_clock,
        waktu_selesai__gte=current_clock,
    ).order_by('waktu_mulai').first()


class ModulManageRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not can_manage_lab_operations(pengguna):
            messages.error(request, 'Hanya laboran yang bisa mengelola modul praktikum.')
            return redirect('asleb:absensi_list')
        return super().dispatch(request, *args, **kwargs)


class ModulPraktikumCreateView(ModulManageRequiredMixin, CreateView):
    model = ModulPraktikum
    form_class = ModulPraktikumForm
    template_name = 'asleb/modul_form.html'
    success_url = reverse_lazy('asleb:absensi_list')

    def form_valid(self, form):
        form.instance.diunggah_oleh = getattr(self.request, 'current_pengguna', None)
        messages.success(self.request, 'Modul praktikum berhasil ditambahkan.')
        return super().form_valid(form)


class ModulPraktikumUpdateView(ModulManageRequiredMixin, UpdateView):
    model = ModulPraktikum
    form_class = ModulPraktikumForm
    template_name = 'asleb/modul_form.html'
    success_url = reverse_lazy('asleb:absensi_list')

    def form_valid(self, form):
        form.instance.diunggah_oleh = getattr(self.request, 'current_pengguna', None)
        messages.success(self.request, 'Modul praktikum berhasil diperbarui.')
        return super().form_valid(form)


class ModulPraktikumDeleteView(ModulManageRequiredMixin, PostOnlyDeleteMixin, DeleteView):
    model = ModulPraktikum
    success_url = reverse_lazy('asleb:absensi_list')

    def form_valid(self, form):
        if self.object.absensi.exists():
            messages.error(self.request, 'Modul yang sudah digunakan untuk absensi tidak dapat dihapus.')
            return redirect(self.success_url)
        messages.success(self.request, 'Modul praktikum berhasil dihapus.')
        return super().form_valid(form)


def get_praktikum_matkul_queryset(pengguna):
    from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb, RiwayatAsleb

    queryset = MataKuliahAsleb.objects.filter(aktif=True)
    if not pengguna:
        return queryset.none()
    if pengguna.role == LABORAN_ROLE:
        return queryset
    if pengguna.role != ASISTEN_LAB_ROLE:
        return queryset.none()

    matkul_ids = PendaftaranAsleb.objects.filter(
        nim=pengguna.nim_nik,
        status__in=['diterima', 'digenerate'],
    ).values_list('matkul_id', flat=True)
    history_ids = RiwayatAsleb.objects.filter(nim=pengguna.nim_nik).values_list('matkul_id', flat=True)
    combined_ids = set(matkul_ids) | set(history_ids)
    if combined_ids:
        return queryset.filter(pk__in=combined_ids)

    asleb = Asleb.objects.filter(nim=pengguna.nim_nik).first()
    fallback = get_asleb_matkul(asleb) if asleb else None
    return queryset.filter(pk=fallback.pk) if fallback else queryset.none()


class PraktikumMahasiswaAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role not in {LABORAN_ROLE, ASISTEN_LAB_ROLE}:
            messages.error(request, 'Anda tidak memiliki akses ke nilai dan absensi mahasiswa.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)


class PesertaPraktikumManageMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not can_manage_lab_operations(pengguna):
            messages.error(request, 'Hanya laboran yang dapat mengelola peserta praktikum.')
            return redirect('asleb:praktikum_mahasiswa_list')
        return super().dispatch(request, *args, **kwargs)


class PraktikumMahasiswaListView(PraktikumMahasiswaAccessMixin, TemplateView):
    template_name = 'asleb/praktikum_mahasiswa_list.html'

    def attach_participant_summaries(self, peserta_list):
        if not peserta_list:
            return
        nilai_summary = {
            item['peserta_id']: item
            for item in HasilPraktikumMahasiswa.objects.filter(
                peserta__in=peserta_list,
                nilai__isnull=False,
            ).values('peserta_id').annotate(
                rata_rata=Avg('nilai'),
                jumlah_nilai=Count('id'),
            )
        }
        for peserta in peserta_list:
            summary = nilai_summary.get(peserta.pk, {})
            peserta.rata_rata_nilai = summary.get('rata_rata')
            peserta.jumlah_nilai = summary.get('jumlah_nilai', 0)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pengguna = self.request.current_pengguna
        base_matkul_qs = get_praktikum_matkul_queryset(pengguna).order_by('nama', 'kelas')
        class_options = list(
            base_matkul_qs.exclude(kelas='').values_list('kelas', flat=True).distinct().order_by('kelas')
        )
        selected_kelas = self.request.GET.get('kelas', '').strip()
        if selected_kelas:
            base_matkul_qs = base_matkul_qs.filter(kelas=selected_kelas)
        matkul_list = list(
            base_matkul_qs
            .prefetch_related('modul_praktikum')
        )
        for matkul in matkul_list:
            matkul.jumlah_peserta = matkul.peserta_praktikum.filter(aktif=True).count()
            matkul.modul_tersedia = list(matkul.modul_praktikum.all())
            matkul.peserta_modal_list = list(matkul.peserta_praktikum.select_related('pengguna').all())
            self.attach_participant_summaries(matkul.peserta_modal_list)

        selected_id = self.request.GET.get('matkul', '').strip()
        selected_matkul = next((item for item in matkul_list if str(item.pk) == selected_id), None)
        if not selected_matkul and len(matkul_list) == 1:
            selected_matkul = matkul_list[0]
        peserta_list = selected_matkul.peserta_modal_list if selected_matkul else []
        rekap_matkul = selected_matkul or (matkul_list[0] if matkul_list else None)
        rekap_hasil = list(
            HasilPraktikumMahasiswa.objects
            .select_related('peserta', 'modul', 'modul__matkul')
            .filter(modul__matkul=rekap_matkul)
            .order_by('peserta_nama', 'peserta__nama', 'modul__nomor')
        ) if rekap_matkul else []
        rekap_data = build_rekap_nilai_matkul(rekap_matkul, rekap_hasil) if rekap_matkul else {
            'modules': [],
            'rows': [],
            'total_mahasiswa': 0,
            'nilai_terisi': 0,
            'nilai_target': 0,
            'kelengkapan': 0,
        }
        total_modul = sum(len(item.modul_tersedia) for item in matkul_list)
        total_mahasiswa = sum(item.jumlah_peserta for item in matkul_list)

        context.update({
            'matkul_list': matkul_list,
            'selected_matkul': selected_matkul,
            'rekap_matkul': rekap_matkul,
            'rekap_modules': rekap_data['modules'],
            'rekap_rows': rekap_data['rows'],
            'rekap_summary': {
                'total_mahasiswa': total_mahasiswa,
                'jumlah_matkul': len(matkul_list),
                'jumlah_modul': total_modul,
                'kelengkapan': rekap_data['kelengkapan'],
            },
            'class_options': class_options,
            'selected_kelas': selected_kelas,
            'peserta_list': peserta_list,
            'selected_matkul_id': selected_id,
            'can_manage_peserta': pengguna.role == LABORAN_ROLE,
            'is_asisten_lab': pengguna.role == ASISTEN_LAB_ROLE,
            'show_peserta_modal': self.request.GET.get('show_peserta') == '1',
        })
        return context


class PesertaPraktikumBulkCreateView(PesertaPraktikumManageMixin, FormView):
    form_class = PesertaPraktikumBulkForm
    template_name = 'asleb/peserta_praktikum_form.html'
    success_url = reverse_lazy('asleb:praktikum_mahasiswa_list')

    def form_valid(self, form):
        matkul = form.cleaned_data['matkul']
        created = 0
        updated = 0
        with transaction.atomic():
            for row in form.cleaned_data['peserta_rows']:
                account = Pengguna.objects.filter(nim_nik=row['nim']).first()
                _, was_created = PesertaPraktikum.objects.update_or_create(
                    matkul=matkul,
                    nim=row['nim'],
                    defaults={
                        'nama': row['nama'],
                        'pengguna': account,
                        'aktif': True,
                        'dibuat_oleh': self.request.current_pengguna,
                    },
                )
                created += int(was_created)
                updated += int(not was_created)
        messages.success(self.request, f'{created} peserta ditambahkan dan {updated} peserta diperbarui.')
        return redirect(f'{self.success_url}?matkul={matkul.pk}')


class PesertaPraktikumUpdateView(PesertaPraktikumManageMixin, UpdateView):
    model = PesertaPraktikum
    form_class = PesertaPraktikumForm
    template_name = 'asleb/peserta_praktikum_form.html'

    def form_valid(self, form):
        account = Pengguna.objects.filter(nim_nik=form.cleaned_data['nim']).first()
        form.instance.pengguna = account
        messages.success(self.request, 'Data peserta praktikum berhasil diperbarui.')
        return super().form_valid(form)

    def get_success_url(self):
        return f'{reverse_lazy("asleb:praktikum_mahasiswa_list")}?matkul={self.object.matkul_id}'


def delete_participant(peserta):
    if peserta.hasil_praktikum.exists():
        peserta.aktif = False
        peserta.save(update_fields=['aktif', 'diperbarui_pada'])
        return 'deactivated'
    peserta.delete()
    return 'deleted'


@require_POST
def delete_peserta_praktikum(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    if not can_manage_lab_operations(pengguna):
        messages.error(request, 'Hanya laboran yang dapat menghapus peserta praktikum.')
        return redirect('asleb:praktikum_mahasiswa_list')
    peserta = get_object_or_404(PesertaPraktikum.objects.select_related('matkul'), pk=pk)
    matkul_id = peserta.matkul_id
    result = delete_participant(peserta)
    if result == 'deactivated':
        messages.success(request, 'Peserta dinonaktifkan agar riwayat nilai dan absensi tetap tersimpan.')
    else:
        messages.success(request, 'Peserta praktikum berhasil dihapus.')
    return redirect(f'{reverse_lazy("asleb:praktikum_mahasiswa_list")}?matkul={matkul_id}')


@require_POST
def bulk_delete_peserta_praktikum(request):
    pengguna = getattr(request, 'current_pengguna', None)
    if not can_manage_lab_operations(pengguna):
        messages.error(request, 'Hanya laboran yang dapat menghapus peserta praktikum.')
        return redirect('asleb:praktikum_mahasiswa_list')
    participant_ids = request.POST.getlist('peserta_ids')
    matkul_id = request.POST.get('matkul_id', '').strip()
    peserta_queryset = PesertaPraktikum.objects.filter(pk__in=participant_ids)
    if matkul_id:
        peserta_queryset = peserta_queryset.filter(matkul_id=matkul_id)
    deleted = 0
    deactivated = 0
    for peserta in peserta_queryset:
        result = delete_participant(peserta)
        deleted += int(result == 'deleted')
        deactivated += int(result == 'deactivated')
    if deleted or deactivated:
        messages.success(request, f'{deleted} peserta dihapus dan {deactivated} peserta dinonaktifkan.')
    else:
        messages.error(request, 'Pilih minimal satu peserta untuk dihapus.')
    redirect_url = reverse_lazy('asleb:praktikum_mahasiswa_list')
    return redirect(f'{redirect_url}?matkul={matkul_id}' if matkul_id else redirect_url)


@require_POST
def delete_all_peserta_praktikum(request, matkul_pk):
    pengguna = getattr(request, 'current_pengguna', None)
    if not can_manage_lab_operations(pengguna):
        messages.error(request, 'Hanya laboran yang dapat menghapus peserta praktikum.')
        return redirect('asleb:praktikum_mahasiswa_list')
    matkul = get_object_or_404(get_praktikum_matkul_queryset(pengguna), pk=matkul_pk)
    peserta_qs = matkul.peserta_praktikum.all()
    total = peserta_qs.count()
    with transaction.atomic():
        peserta_with_history = peserta_qs.filter(hasil_praktikum__isnull=False).distinct()
        peserta_with_history.update(aktif=False)
        peserta_qs.filter(hasil_praktikum__isnull=True).delete()
    messages.success(request, f'{total} peserta praktikum berhasil dihapus dari daftar. Riwayat nilai tetap disimpan.')
    return redirect(f'{reverse_lazy("asleb:praktikum_mahasiswa_list")}?matkul={matkul.pk}')


class NilaiAbsensiMahasiswaView(PraktikumMahasiswaAccessMixin, TemplateView):
    template_name = 'asleb/nilai_absensi_mahasiswa.html'

    def dispatch(self, request, *args, **kwargs):
        self.matkul = get_object_or_404(get_praktikum_matkul_queryset(getattr(request, 'current_pengguna', None)), pk=kwargs['matkul_pk'])
        self.modul = get_object_or_404(ModulPraktikum, pk=kwargs['modul_pk'], matkul=self.matkul)
        return super().dispatch(request, *args, **kwargs)

    def build_rows(self, data=None):
        peserta_list = self.matkul.peserta_praktikum.filter(aktif=True).order_by('nama')
        existing = {
            item.peserta_id: item
            for item in HasilPraktikumMahasiswa.objects.filter(peserta__in=peserta_list, modul=self.modul)
        }
        return [
            {
                'peserta': peserta,
                'form': HasilPraktikumMahasiswaForm(
                    data=data,
                    instance=existing.get(peserta.pk),
                    prefix=f'peserta-{peserta.pk}',
                ),
                'rata_rata': existing[peserta.pk].nilai_rata_rata_display if peserta.pk in existing else '-',
            }
            for peserta in peserta_list
        ]

    def post(self, request, *args, **kwargs):
        rows = self.build_rows(request.POST)
        tanggal = request.POST.get('tanggal_praktikum', '').strip()
        from django.utils.dateparse import parse_date
        tanggal_praktikum = parse_date(tanggal)
        forms_valid = all([row['form'].is_valid() for row in rows])
        if not tanggal_praktikum:
            messages.error(request, 'Tanggal praktikum wajib diisi dengan format yang valid.')
            forms_valid = False
        if forms_valid:
            with transaction.atomic():
                for row in rows:
                    result = row['form'].save(commit=False)
                    result.peserta = row['peserta']
                    result.modul = self.modul
                    result.tanggal_praktikum = tanggal_praktikum
                    result.dicatat_oleh = request.current_pengguna
                    result.full_clean()
                    result.save()
            messages.success(request, f'Nilai dan absensi {len(rows)} mahasiswa berhasil disimpan.')
            return redirect('asleb:praktikum_nilai', matkul_pk=self.matkul.pk, modul_pk=self.modul.pk)
        return self.render_to_response(self.get_context_data(rows=rows, tanggal_praktikum=tanggal))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'matkul': self.matkul,
            'modul': self.modul,
            'rows': kwargs.get('rows') or self.build_rows(),
            'tanggal_praktikum': kwargs.get('tanggal_praktikum') or timezone.localdate().isoformat(),
            'is_asisten_lab': self.request.current_pengguna.role == ASISTEN_LAB_ROLE,
        })
        return context


def export_nilai_praktikum_excel(request):
    pengguna = getattr(request, 'current_pengguna', None)
    if not pengguna or pengguna.role not in {LABORAN_ROLE, ASISTEN_LAB_ROLE}:
        messages.error(request, 'Anda tidak memiliki akses mengunduh rekap nilai praktikum.')
        return redirect('dashboard:home')

    matkul_qs = get_praktikum_matkul_queryset(pengguna)
    matkul_id = request.GET.get('matkul', '').strip()
    matkul_list = list(matkul_qs.order_by('nama', 'kelas'))
    hasil_qs = (
        HasilPraktikumMahasiswa.objects
        .select_related('peserta', 'modul', 'modul__matkul', 'dicatat_oleh')
        .filter(modul__matkul__in=matkul_qs)
        .order_by('modul__matkul__nama', 'modul__matkul__kelas', 'modul__nomor', 'peserta_nama')
    )
    if matkul_id:
        hasil_qs = hasil_qs.filter(modul__matkul_id=matkul_id)
        matkul_list = [item for item in matkul_list if str(item.pk) == matkul_id]
    hasil_list = list(hasil_qs)

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        used_names = set()
        for matkul in matkul_list:
            matkul_results = [hasil for hasil in hasil_list if hasil.modul.matkul_id == matkul.pk]
            rekap = build_rekap_nilai_matkul(matkul, matkul_results)
            rows = build_rekap_nilai_excel_rows(matkul, rekap)
            base_filename = slugify(f'{matkul.nama}-{matkul.kelas}') or f'rekap-nilai-{matkul.pk}'
            filename = base_filename
            if filename in used_names:
                filename = f'{base_filename}-{matkul.pk}'
            used_names.add(filename)
            archive.writestr(f'{filename}.xlsx', build_simple_xlsx(rows, sheet_name='Rekap Nilai'))
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    zip_suffix = ''
    if len(matkul_list) == 1:
        zip_suffix = '-' + (slugify(f'{matkul_list[0].nama}-{matkul_list[0].kelas}') or str(matkul_list[0].pk))
    response['Content-Disposition'] = f'attachment; filename="rekap-nilai-per-mata-kuliah{zip_suffix}.zip"'
    return response


def build_rekap_nilai_matkul(matkul, hasil_list):
    if not matkul:
        return {'modules': [], 'rows': [], 'total_mahasiswa': 0, 'nilai_terisi': 0, 'nilai_target': 0, 'kelengkapan': 0}

    modules = list(ModulPraktikum.objects.filter(matkul=matkul).order_by('nomor', 'pk'))
    peserta_map = {}
    for peserta in matkul.peserta_praktikum.filter(aktif=True).order_by('nama', 'nim'):
        peserta_map[peserta.nim] = {
            'nim': peserta.nim,
            'nama': peserta.nama,
            'kelas': matkul.kelas,
            'matkul': matkul.nama,
            'module_scores': {},
        }

    for hasil in hasil_list:
        nim = hasil.peserta.nim if hasil.peserta_id else hasil.peserta_nim
        if not nim:
            continue
        peserta_map.setdefault(nim, {
            'nim': nim,
            'nama': hasil.peserta.nama if hasil.peserta_id else hasil.peserta_nama,
            'kelas': matkul.kelas,
            'matkul': matkul.nama,
            'module_scores': {},
        })
        score = hasil.hitung_nilai_rata_rata()
        if score is not None:
            peserta_map[nim]['module_scores'][hasil.modul.nomor] = score

    rows = []
    nilai_terisi = 0
    for index, row in enumerate(sorted(peserta_map.values(), key=lambda item: (item['nama'], item['nim'])), start=1):
        scores = [row['module_scores'].get(module.nomor) for module in modules]
        filled_scores = [score for score in scores if score is not None]
        total = sum(filled_scores, Decimal('0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if filled_scores else None
        average = (total / Decimal(len(filled_scores))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if filled_scores else None
        nilai_terisi += len(filled_scores)
        row.update({
            'no': index,
            'scores': scores,
            'total': total,
            'average': average,
            'keterangan': 'Lengkap' if modules and len(filled_scores) == len(modules) else 'Belum lengkap',
        })
        rows.append(row)

    nilai_target = len(rows) * len(modules)
    kelengkapan = round((nilai_terisi / nilai_target) * 100) if nilai_target else 0
    return {
        'modules': modules,
        'rows': rows,
        'total_mahasiswa': len(rows),
        'nilai_terisi': nilai_terisi,
        'nilai_target': nilai_target,
        'kelengkapan': kelengkapan,
    }


def build_rekap_nilai_excel_rows(matkul, rekap):
    headers = ['No', 'NIM', 'Nama Mahasiswa', 'Kelas', 'Mata Kuliah']
    headers.extend([f'Modul {module.nomor}' for module in rekap['modules']])
    headers.extend(['Total Nilai', 'Rata-rata Nilai', 'Keterangan'])
    rows = [headers]
    for row in rekap['rows']:
        values = [row['no'], row['nim'], row['nama'], row['kelas'], row['matkul']]
        values.extend('' if score is None else f'{score:.2f}' for score in row['scores'])
        values.extend([
            '' if row['total'] is None else f'{row["total"]:.2f}',
            '' if row['average'] is None else f'{row["average"]:.2f}',
            row['keterangan'],
        ])
        rows.append(values)
    if len(rows) == 1 and matkul:
        rows.append(['', '', 'Belum ada data nilai', matkul.kelas, matkul.nama] + [''] * (len(headers) - 5))
    return rows


def build_nilai_praktikum_rows(hasil_list):
    nilai_by_nim = {}
    for hasil in hasil_list:
        nim = hasil.peserta.nim if hasil.peserta_id else hasil.peserta_nim
        nilai = hasil.hitung_nilai_rata_rata()
        if nim and nilai is not None:
            nilai_by_nim.setdefault(nim, []).append(nilai)
    rata_rata_mahasiswa = {
        nim: (sum(values, Decimal('0')) / Decimal(len(values))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        for nim, values in nilai_by_nim.items()
        if values
    }

    rows = [[
        'Mata Kuliah',
        'Kelas',
        'Dosen',
        'Modul',
        'Tanggal Praktikum',
        'NIM',
        'Nama Mahasiswa',
        'Status Absensi',
        'Nilai Realtime',
        'Nilai Laporan',
        'Rata-rata Modul',
        'Rata-rata Mahasiswa',
        'Catatan',
        'Dicatat Oleh',
    ]]
    for hasil in hasil_list:
        matkul = hasil.modul.matkul
        nim = hasil.peserta.nim if hasil.peserta_id else hasil.peserta_nim
        rows.append([
            matkul.nama,
            matkul.kelas,
            matkul.dosen,
            f'Modul {hasil.modul.nomor} - {hasil.modul.judul}',
            hasil.tanggal_praktikum.isoformat(),
            nim,
            hasil.peserta.nama if hasil.peserta_id else hasil.peserta_nama,
            hasil.get_status_absensi_display(),
            '' if hasil.nilai_realtime is None else str(hasil.nilai_realtime),
            '' if hasil.nilai_laporan is None else str(hasil.nilai_laporan),
            '' if hasil.hitung_nilai_rata_rata() is None else str(hasil.hitung_nilai_rata_rata()),
            '' if nim not in rata_rata_mahasiswa else str(rata_rata_mahasiswa[nim]),
            hasil.catatan,
            hasil.dicatat_oleh.nama_pengguna if hasil.dicatat_oleh_id else '',
        ])
    return rows


def build_simple_xlsx(rows, sheet_name='Sheet1'):
    def col_name(index):
        name = ''
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(65 + remainder) + name
        return name

    column_widths = []
    for col_index in range(1, (len(rows[0]) if rows else 1) + 1):
        max_length = max((len(str(row[col_index - 1])) for row in rows if len(row) >= col_index), default=10)
        column_widths.append(min(max(max_length + 4, 12), 34))
    cols = ''.join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(column_widths, start=1)
    )

    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            coordinate = f'{col_name(col_index)}{row_index}'
            safe_value = escape(str(value or ''))
            style = ' s="1"' if row_index == 1 else ' s="2"'
            cells.append(f'<c r="{coordinate}"{style} t="inlineStr"><is><t>{safe_value}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    last_col = col_name(len(rows[0])) if rows and rows[0] else 'A'
    last_row = max(len(rows), 1)
    worksheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>{cols}</cols>
  <sheetData>{''.join(sheet_rows)}</sheetData>
  <autoFilter ref="A1:{last_col}{last_row}"/>
</worksheet>'''
    workbook = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF0F766E"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FFE2E8F0"/></left><right style="thin"><color rgb="FFE2E8F0"/></right><top style="thin"><color rgb="FFE2E8F0"/></top><bottom style="thin"><color rgb="FFE2E8F0"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

    output = BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', content_types)
        archive.writestr('_rels/.rels', root_rels)
        archive.writestr('xl/workbook.xml', workbook)
        archive.writestr('xl/_rels/workbook.xml.rels', workbook_rels)
        archive.writestr('xl/worksheets/sheet1.xml', worksheet)
        archive.writestr('xl/styles.xml', styles)
    return output.getvalue()


def download_modul_praktikum(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    modul = get_object_or_404(ModulPraktikum.objects.select_related('matkul'), pk=pk)
    allowed = can_manage_lab_operations(pengguna)

    if pengguna and pengguna.role == ASISTEN_LAB_ROLE:
        asleb = Asleb.objects.filter(nim=pengguna.nim_nik).first()
        allowed = bool(asleb and get_asleb_matkul(asleb) == modul.matkul)

    if not allowed:
        messages.error(request, 'Anda tidak memiliki akses ke modul praktikum ini.')
        return redirect('asleb:absensi_list')

    return FileResponse(
        modul.file.open('rb'),
        as_attachment=True,
        filename=modul.file.name.rsplit('/', 1)[-1],
    )


@require_POST
def toggle_absensi_status(request):
    pengguna = getattr(request, 'current_pengguna', None)
    if not can_manage_lab_operations(pengguna):
        messages.error(request, 'Hanya laboran yang bisa membuka atau menutup absensi.')
        return redirect('asleb:absensi_list')

    pengaturan = PengaturanAbsensiAsleb.get_solo()
    pengaturan.dibuka = not pengaturan.dibuka
    pengaturan.save(update_fields=['dibuka', 'diperbarui_pada'])

    status = 'dibuka' if pengaturan.dibuka else 'ditutup'
    messages.success(request, f'Absensi aslab berhasil {status}.')
    return redirect('asleb:absensi_list')


@require_POST
def confirm_honor_transfer(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    if not can_manage_lab_operations(pengguna):
        messages.error(request, 'Hanya laboran yang bisa mengonfirmasi transfer honor.')
        return redirect('asleb:honor_list')

    honor = get_object_or_404(HonorAsleb, pk=pk)
    if pengguna.role == LABORAN_ROLE and honor.assigned_laboran_id != pengguna.pk:
        messages.error(request, 'Tugas TF honor ini bukan milik akun laboran Anda.')
        return redirect('asleb:honor_list')

    form = KonfirmasiTransferHonorForm(request.POST, request.FILES, instance=honor)

    if not form.is_valid():
        messages.error(request, 'Konfirmasi transfer gagal. Pastikan tanggal, PIC, dan bukti transfer sudah diisi dengan benar.')
        return redirect('asleb:honor_list')

    honor = form.save(commit=False)
    if not honor.tanggal_transfer:
        honor.tanggal_transfer = timezone.localdate()
    if not honor.pic_transfer:
        honor.pic_transfer = pengguna.nama_pengguna
    honor.status = 'dibayar'
    honor.save()
    transaction.on_commit(lambda: send_honor_update(honor, event='honor.paid'))
    messages.success(request, f'Honor {honor.asleb.nama} berhasil dikonfirmasi sudah ditransfer.')
    return redirect('asleb:honor_list')


@require_POST
def auto_assign_honor_transfers(request):
    pengguna = getattr(request, 'current_pengguna', None)
    if not can_manage_lab_operations(pengguna):
        messages.error(request, 'Hanya laboran yang bisa membagi tugas TF otomatis.')
        return redirect('asleb:honor_list')

    selected_bulan = request.POST.get('bulan', '').strip()
    honor_qs = HonorAsleb.objects.select_related('asleb').filter(assigned_laboran__isnull=True).order_by('bulan', 'asleb__nama', 'pk')
    if selected_bulan:
        try:
            year, month = selected_bulan.split('-')
            honor_qs = honor_qs.filter(bulan__year=year, bulan__month=month)
        except ValueError:
            messages.error(request, 'Format bulan tidak valid.')
            return redirect('asleb:honor_list')

    with transaction.atomic():
        assigned_count = assign_unassigned_honor_transfers(honor_qs)

    if assigned_count:
        messages.success(request, f'{assigned_count} tugas TF honor berhasil dibagi otomatis ke laboran.')
    else:
        messages.info(request, 'Tidak ada honor yang perlu dibagi, atau belum ada akun laboran terverifikasi.')
    return redirect('asleb:honor_list')


def assign_unassigned_honor_transfers(honor_qs):
    assigned_count = 0
    for honor in honor_qs:
        laboran = honor.get_next_laboran_for_transfer()
        if not laboran:
            continue
        honor.assigned_laboran = laboran
        honor.save(update_fields=['assigned_laboran', 'level', 'jumlah', 'diperbarui_pada'])
        assigned_count += 1
    return assigned_count


def cleanup_expired_surat_honor():
    today = timezone.localdate()
    for surat in SuratHonorAsleb.objects.filter(expires_at__lt=today):
        if surat.file_pdf:
            surat.file_pdf.delete(save=False)
        surat.delete()


def roman_month(month):
    numerals = {
        1: 'I',
        2: 'II',
        3: 'III',
        4: 'IV',
        5: 'V',
        6: 'VI',
        7: 'VII',
        8: 'VIII',
        9: 'IX',
        10: 'X',
        11: 'XI',
        12: 'XII',
    }
    return numerals[month]


def sync_honor_from_absensi(absensi):
    bulan = absensi.tanggal_praktikum.replace(day=1)
    total_pertemuan = AbsensiAsleb.objects.filter(
        asleb=absensi.asleb,
        tanggal_praktikum__year=bulan.year,
        tanggal_praktikum__month=bulan.month,
    ).count()

    honor, _ = HonorAsleb.objects.get_or_create(
        asleb=absensi.asleb,
        bulan=bulan,
        defaults={
            'jumlah_praktikum': 1,
            'pic_transfer': '',
            'status': 'diproses',
        },
    )
    honor.jumlah_praktikum = max(honor.jumlah_praktikum, 1)
    honor.total_pertemuan = total_pertemuan
    if honor.status == 'draft':
        honor.status = 'diproses'
    honor.save()
    return honor
