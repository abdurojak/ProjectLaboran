import logging
import mimetypes
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from html import escape

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.utils.http import content_disposition_header
from django.utils.text import slugify
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from apps.core.views import PostOnlyDeleteMixin
from apps.core.permissions import ASISTEN_LAB_ROLE, LABORAN_ROLE, MAHASISWA_ROLE, can_manage_lab_operations
from apps.jadwal.models import JadwalPraktikum
from apps.kalender.realtime import send_attendance_update, send_honor_update
from apps.pengguna.models import Pengguna
from apps.pendaftaran_asleb.forms import PengaturanBiayaTransferForm
from apps.pendaftaran_asleb.models import AslabAssignment, PengaturanBiayaTransfer
from apps.pendaftaran_asleb.replacement_services import (
    end_single_active_assignment_for_replacement,
    payment_eligible_honors,
    with_replacement_hold_state,
)
from apps.pendaftaran_asleb.services import notify_manual_asleb_removal

from .forms import (
    AbsensiAslebForm,
    AslebForm,
    ENABLE_CAMERA_LOCATION_CAPTURE,
    HonorAslebForm,
    KonfirmasiTransferHonorForm,
    HasilPraktikumMahasiswaForm,
    ModulPraktikumForm,
    PengumpulanLaporanPraktikumForm,
    PesertaPraktikumBulkForm,
    PesertaPraktikumForm,
    ReviewLaporanPraktikumForm,
    SuratHonorAslebGenerateForm,
    TugasLaporanPraktikumForm,
    get_asleb_matkul,
)
from .models import (
    AbsensiAsleb,
    AbsensiMasukAsleb,
    Asleb,
    HasilPraktikumMahasiswa,
    HonorAsleb,
    LogAktivitasPraktikum,
    ModulPraktikum,
    PengumpulanLaporanPraktikum,
    PengaturanAbsensiAsleb,
    PesertaPraktikum,
    SuratHonorAsleb,
    TugasLaporanPraktikum,
)
from .surat_honor import generate_surat_honor_pdf, month_year_label


logger = logging.getLogger(__name__)


def nilai_huruf(nilai):
    if nilai is None:
        return '-'
    nilai = Decimal(nilai)
    if nilai >= Decimal('80'):
        return 'A'
    if nilai >= Decimal('70'):
        return 'B'
    return 'C'


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
    alasan_pengeluaran = request.POST.get('alasan_pengeluaran', '').strip()
    if not alasan_pengeluaran:
        messages.error(request, 'Alasan pengeluaran Aslab wajib diisi sebelum akun dinonaktifkan.')
        return redirect('asleb:asleb_list')

    try:
        end_single_active_assignment_for_replacement(
            asleb_id=asleb.pk,
            actor=pengguna,
            reason_type='dismissal',
            reason=alasan_pengeluaran,
            effective_date=timezone.localdate(),
        )
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
        return redirect('asleb:asleb_list')

    asleb.refresh_from_db()
    akun = Pengguna.objects.filter(nim_nik=asleb.nim).first()
    person_access_ended = (
        asleb.status == 'nonaktif'
        and akun is not None
        and akun.role == MAHASISWA_ROLE
        and not AslabAssignment.objects.filter(
            asleb=asleb,
            status=AslabAssignment.STATUS_ACTIVE,
        ).exists()
    )
    if person_access_ended:
        transaction.on_commit(
            lambda asleb_item=asleb, akun_item=akun, reason=alasan_pengeluaran, actor=pengguna:
            notify_manual_asleb_removal(asleb_item, akun_item, reason=reason, acted_by=actor)
        )

    if person_access_ended:
        messages.success(
            request,
            f'{asleb.nama} dikeluarkan dari Aslab dan proses penggantian berhasil dibuat. '
            'notifikasi telah dikirim.',
        )
    else:
        messages.success(
            request,
            f'Satu penugasan Aslab {asleb.nama} telah diakhiri dan proses penggantian berhasil dibuat.',
        )
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
        queryset = with_replacement_hold_state(
            HonorAsleb.objects.select_related('asleb', 'assigned_laboran')
        )
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
        context['formula_note'] = 'Total Honor = Status Aslab (Senior/Junior x (Jumlah Modul x Total Pertemuan )) = *7 jam /modul maximal 60 jam /bulan. Level otomatis: periode aslab ke-1 dan ke-2 Junior Rp7.000, mulai ke-3 Senior Rp8.000.'
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
        for honor in payment_eligible_honors(HonorAsleb.objects.exclude(status='dibayar')):
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

    @transaction.atomic
    def form_valid(self, form):
        pengguna = getattr(self.request, 'current_pengguna', None)
        bulan = form.cleaned_data['bulan']
        honors = list(payment_eligible_honors(
            HonorAsleb.objects.select_for_update().select_related('asleb').filter(
            bulan__year=bulan.year,
            bulan__month=bulan.month,
            )
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
        surat.honors.set(honors)
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
        queryset = AbsensiAsleb.objects.select_related('asleb', 'modul_praktikum', 'modul_praktikum__matkul')
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
        context['mobile_absensi_list'] = self.get_mobile_absensi_queryset(pengguna)
        return context

    def get_mobile_absensi_queryset(self, pengguna):
        queryset = AbsensiMasukAsleb.objects.select_related(
            'asleb',
            'jadwal',
            'jadwal__ruangan',
            'jadwal__ruangan_tambahan',
        )
        search = self.request.GET.get('q', '').strip()

        if pengguna and pengguna.role == ASISTEN_LAB_ROLE:
            queryset = queryset.filter(asleb__nim=pengguna.nim_nik)
        elif pengguna and pengguna.role != LABORAN_ROLE:
            queryset = queryset.none()

        if search:
            queryset = queryset.filter(
                Q(asleb__nama__icontains=search) |
                Q(asleb__nim__icontains=search) |
                Q(jadwal__mata_kuliah__icontains=search) |
                Q(jadwal__kelas__icontains=search)
            )

        return queryset[:50]

    def get_modul_list(self, pengguna, asleb_profile):
        queryset = ModulPraktikum.objects.select_related('matkul', 'diunggah_oleh')
        if pengguna and pengguna.role == ASISTEN_LAB_ROLE:
            matkul = get_asleb_matkul(asleb_profile) if asleb_profile else None
            return queryset.filter(matkul=matkul) if matkul else queryset.none()
        return queryset

    def get_asleb_profile(self, pengguna):
        if not pengguna or pengguna.role != ASISTEN_LAB_ROLE:
            return None

        return (
            Asleb.objects.filter(nim=pengguna.nim_nik, status='aktif')
            .order_by('-diperbarui_pada', '-pk')
            .first()
        )


class AbsensiAslebCreateView(CreateView):
    model = AbsensiAsleb
    form_class = AbsensiAslebForm
    template_name = 'asleb/absensi_form.html'
    success_url = reverse_lazy('asleb:absensi_list')

    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        self.asleb = (
            Asleb.objects.filter(nim=getattr(pengguna, 'nim_nik', ''), status='aktif')
            .order_by('-diperbarui_pada', '-pk')
            .first()
        )

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
        try:
            response = super().form_valid(form)
        except IntegrityError:
            modul = form.cleaned_data.get('modul_praktikum')
            if modul:
                form.add_error(
                    'modul_praktikum',
                    f'Modul {modul.nomor} sudah pernah diabsen. Data tidak disimpan dua kali.'
                )
            else:
                form.add_error(None, 'Absensi modul ini sudah pernah tersimpan sebelumnya.')
            return self.form_invalid(form)
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
    allowed_bulk_extensions = {'.pdf', '.doc', '.docx'}
    max_bulk_file_size = 15 * 1024 * 1024

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['existing_modules'] = (
            ModulPraktikum.objects.select_related('matkul', 'diunggah_oleh')
            .order_by('matkul__nama', 'matkul__kelas', 'nomor')[:18]
        )
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('bulk_upload') == '1':
            return self.handle_bulk_upload(request)
        return super().post(request, *args, **kwargs)

    def handle_bulk_upload(self, request):
        from apps.pendaftaran_asleb.models import MataKuliahAsleb

        matkul = get_object_or_404(MataKuliahAsleb, pk=request.POST.get('bulk_matkul'), aktif=True)
        files = request.FILES.getlist('bulk_files')
        titles = request.POST.getlist('bulk_judul')
        uploader = getattr(request, 'current_pengguna', None)

        if not files:
            messages.error(request, 'Pilih minimal satu file modul terlebih dahulu.')
            return redirect('asleb:modul_create')

        errors = []
        for uploaded in files:
            lower_name = uploaded.name.lower()
            extension = lower_name[lower_name.rfind('.'):] if '.' in lower_name else ''
            if extension not in self.allowed_bulk_extensions:
                errors.append(f'{uploaded.name}: File modul hanya boleh PDF atau Word.')
            if uploaded.size > self.max_bulk_file_size:
                errors.append(f'{uploaded.name}: ukuran maksimal 15 MB.')

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('asleb:modul_create')

        last_number = (
            ModulPraktikum.objects
            .filter(matkul=matkul)
            .order_by('-nomor')
            .values_list('nomor', flat=True)
            .first()
            or 0
        )

        with transaction.atomic():
            for index, uploaded in enumerate(files, start=1):
                raw_title = titles[index - 1].strip() if index - 1 < len(titles) else ''
                fallback_title = uploaded.name.rsplit('.', 1)[0].replace('-', ' ').replace('_', ' ').strip()
                ModulPraktikum.objects.create(
                    matkul=matkul,
                    nomor=last_number + index,
                    judul=raw_title or fallback_title or f'Modul {last_number + index}',
                    file=uploaded,
                    diunggah_oleh=uploader,
                )

        messages.success(request, f'{len(files)} modul praktikum berhasil diupload sekaligus.')
        return redirect(self.success_url)

    def form_valid(self, form):
        form.instance.diunggah_oleh = getattr(self.request, 'current_pengguna', None)
        messages.success(self.request, 'Modul praktikum berhasil ditambahkan.')
        return super().form_valid(form)


class ModulPraktikumUpdateView(ModulManageRequiredMixin, UpdateView):
    model = ModulPraktikum
    form_class = ModulPraktikumForm
    template_name = 'asleb/modul_form.html'
    success_url = reverse_lazy('asleb:absensi_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['existing_modules'] = (
            ModulPraktikum.objects.select_related('matkul', 'diunggah_oleh')
            .filter(matkul=self.object.matkul)
            .order_by('nomor')
        )
        return context

    def form_valid(self, form):
        form.instance.diunggah_oleh = getattr(self.request, 'current_pengguna', None)
        messages.success(self.request, 'Modul praktikum berhasil diperbarui.')
        return super().form_valid(form)


class ModulPraktikumDeleteView(ModulManageRequiredMixin, PostOnlyDeleteMixin, DeleteView):
    model = ModulPraktikum
    success_url = reverse_lazy('asleb:absensi_list')

    def form_valid(self, form):
        messages.success(
            self.request,
            'Modul praktikum berhasil dihapus. Riwayat absensi dan nilai lama tetap tersimpan sebagai arsip.'
        )
        return super().form_valid(form)


def get_praktikum_matkul_queryset(pengguna):
    from apps.pendaftaran_asleb.models import MataKuliahAsleb

    queryset = MataKuliahAsleb.objects.filter(aktif=True)
    if not pengguna:
        return queryset.none()
    if pengguna.role == LABORAN_ROLE:
        return queryset
    if pengguna.role != ASISTEN_LAB_ROLE:
        return queryset.none()

    active_asleb_rows = list(
        Asleb.objects.filter(nim=pengguna.nim_nik, status='aktif').order_by('-diperbarui_pada', '-pk')
    )
    if active_asleb_rows:
        active_matkul_ids = []
        for asleb in active_asleb_rows:
            matkul = get_asleb_matkul(asleb)
            if matkul and matkul.pk not in active_matkul_ids:
                active_matkul_ids.append(matkul.pk)
        return queryset.filter(pk__in=active_matkul_ids) if active_matkul_ids else queryset.none()

    return queryset.none()


def get_active_asleb_for_matkul(pengguna, matkul):
    if not pengguna or pengguna.role != ASISTEN_LAB_ROLE or not matkul:
        return None
    return (
        Asleb.objects.filter(nim=pengguna.nim_nik, status='aktif', matkul=str(matkul))
        .order_by('-diperbarui_pada', '-pk')
        .first()
    )


def can_review_laporan(pengguna, tugas):
    if not pengguna or pengguna.role != ASISTEN_LAB_ROLE:
        return False
    active_asleb = get_active_asleb_for_matkul(pengguna, tugas.matkul)
    if not active_asleb:
        return False
    return not tugas.asisten_pemeriksa_id or tugas.asisten_pemeriksa_id == active_asleb.pk


def get_participant_for_task(pengguna, tugas):
    if not pengguna:
        return None
    return (
        PesertaPraktikum.objects.filter(
            pengguna=pengguna,
            matkul=tugas.matkul,
            aktif=True,
        )
        .select_related('matkul')
        .first()
    )


def can_access_laporan(pengguna, laporan):
    if not pengguna:
        return False
    if laporan.peserta.pengguna_id == pengguna.pk:
        return True
    return can_review_laporan(pengguna, laporan.tugas)


def sync_laporan_score_to_praktikum_result(laporan, reviewer):
    if laporan.nilai is None or not laporan.tugas.modul_id:
        return None
    hasil, _ = HasilPraktikumMahasiswa.objects.update_or_create(
        peserta=laporan.peserta,
        modul=laporan.tugas.modul,
        defaults={
            'tanggal_praktikum': timezone.localdate(),
            'status_absensi': 'hadir',
            'nilai_laporan': laporan.nilai,
            'dicatat_oleh': reviewer,
            'catatan': laporan.catatan_asisten[:250],
        },
    )
    return hasil


def log_praktikum_activity(pengguna, aksi, deskripsi='', matkul=None, peserta=None):
    LogAktivitasPraktikum.objects.create(
        pengguna=pengguna,
        aksi=aksi,
        deskripsi=deskripsi,
        matkul_label=str(matkul or getattr(peserta, 'matkul', '') or ''),
        peserta_nim=getattr(peserta, 'nim', '') or '',
    )


def notify_pengguna(pengguna, source_key, title, description, url='', badge='Laporan', icon='clipboard-check'):
    if not pengguna:
        return
    from apps.kalender.models import Notifikasi

    Notifikasi.objects.update_or_create(
        pengguna=pengguna,
        source_key=source_key,
        defaults={
            'judul': title,
            'deskripsi': description,
            'tanggal': timezone.localdate(),
            'waktu_label': timezone.localtime().strftime('%H:%M'),
            'url': url,
            'badge': badge,
            'icon': icon,
            'icon_class': 'bg-cyan-100 text-cyan-700',
            'source_updated_at': timezone.now(),
        },
    )


def notify_task_created(tugas, request):
    url = request.build_absolute_uri(reverse_lazy('asleb:laporan_tugas_list'))
    for peserta in tugas.matkul.peserta_praktikum.select_related('pengguna').filter(aktif=True, pengguna__isnull=False):
        notify_pengguna(
            peserta.pengguna,
            f'laporan-task:{tugas.pk}:peserta:{peserta.pk}',
            f'Tugas laporan baru: {tugas.judul}',
            f'{tugas.matkul} memiliki tugas laporan baru. Batas: {timezone.localtime(tugas.batas_pengumpulan):%d %b %Y %H:%M}.',
            url=url,
        )


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
            peserta.nilai_huruf = nilai_huruf(peserta.rata_rata_nilai) if peserta.rata_rata_nilai is not None else '-'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pengguna = self.request.current_pengguna
        base_matkul_qs = get_praktikum_matkul_queryset(pengguna).order_by('nama', 'kelas')
        class_options = list(
            base_matkul_qs.exclude(kelas='').values_list('kelas', flat=True).distinct().order_by('kelas')
        )
        search_query = self.request.GET.get('q', '').strip()
        selected_kelas = self.request.GET.get('kelas', '').strip()
        if search_query:
            base_matkul_qs = base_matkul_qs.filter(
                Q(nama__icontains=search_query)
                | Q(kode__icontains=search_query)
                | Q(kode_mk__icontains=search_query)
                | Q(kelas__icontains=search_query)
                | Q(dosen__icontains=search_query)
            )
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

        effective_selected_id = str(rekap_matkul.pk) if rekap_matkul else ''
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
            'search_query': search_query,
            'peserta_list': peserta_list,
            'selected_matkul_id': effective_selected_id,
            'can_manage_peserta': pengguna.role == LABORAN_ROLE,
            'is_asisten_lab': pengguna.role == ASISTEN_LAB_ROLE,
            'show_peserta_modal': self.request.GET.get('show_peserta') == '1',
        })
        return context


class LaporanPraktikumListView(TemplateView):
    template_name = 'asleb/laporan_praktikum_list.html'

    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna:
            messages.error(request, 'Silakan login untuk membuka laporan praktikum.')
            return redirect('pengguna:login')
        if pengguna.role == LABORAN_ROLE:
            messages.info(request, 'Laboran cukup memantau nilai dan absensi mahasiswa dari menu Nilai & Absensi Mahasiswa.')
            return redirect('asleb:praktikum_mahasiswa_list')
        if pengguna.role not in {MAHASISWA_ROLE, ASISTEN_LAB_ROLE}:
            messages.error(request, 'Anda tidak memiliki akses ke laporan praktikum.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pengguna = self.request.current_pengguna
        peserta_qs = PesertaPraktikum.objects.select_related('matkul').filter(pengguna=pengguna, aktif=True)
        participant_matkul_ids = peserta_qs.values_list('matkul_id', flat=True)
        tugas_peserta = (
            TugasLaporanPraktikum.objects
            .select_related('matkul', 'modul', 'asisten_pemeriksa')
            .filter(aktif=True, matkul_id__in=participant_matkul_ids)
            .order_by('batas_pengumpulan')
        )
        latest_submissions = {}
        for laporan in (
            PengumpulanLaporanPraktikum.objects
            .select_related('tugas', 'peserta')
            .filter(peserta__in=peserta_qs)
            .order_by('tugas_id', 'peserta_id', '-versi')
        ):
            latest_submissions.setdefault((laporan.tugas_id, laporan.peserta_id), laporan)
        participant_cards = []
        peserta_by_matkul = {peserta.matkul_id: peserta for peserta in peserta_qs}
        for tugas in tugas_peserta:
            peserta = peserta_by_matkul.get(tugas.matkul_id)
            participant_cards.append({
                'tugas': tugas,
                'peserta': peserta,
                'laporan': latest_submissions.get((tugas.pk, peserta.pk)) if peserta else None,
            })

        review_tasks = TugasLaporanPraktikum.objects.none()
        if pengguna.role == ASISTEN_LAB_ROLE:
            active_labels = list(
                Asleb.objects.filter(nim=pengguna.nim_nik, status='aktif').exclude(matkul='').values_list('matkul', flat=True)
            )
            review_tasks = TugasLaporanPraktikum.objects.select_related('matkul', 'modul', 'asisten_pemeriksa').filter(
                aktif=True,
                matkul__in=[
                    matkul.pk for matkul in get_praktikum_matkul_queryset(pengguna)
                    if str(matkul) in active_labels
                ],
            )
        submissions_for_review = (
            PengumpulanLaporanPraktikum.objects
            .select_related('tugas', 'tugas__matkul', 'peserta', 'diperiksa_oleh')
            .filter(tugas__in=review_tasks)
            .order_by('tugas__matkul__nama', 'tugas__modul__nomor', 'tugas__judul', '-dikumpulkan_pada')
        )
        review_groups = []
        group_index = {}
        for laporan in submissions_for_review:
            tugas = laporan.tugas
            group_key = tugas.pk
            if group_key not in group_index:
                group_index[group_key] = len(review_groups)
                review_groups.append({
                    'tugas': tugas,
                    'modul_label': f'Modul {tugas.modul.nomor}' if tugas.modul_id else 'Tanpa modul',
                    'laporan_list': [],
                })
            review_groups[group_index[group_key]]['laporan_list'].append(laporan)

        context.update({
            'participant_cards': participant_cards,
            'review_tasks': review_tasks,
            'submissions_for_review': submissions_for_review,
            'review_groups': review_groups,
            'can_create_task': pengguna.role == ASISTEN_LAB_ROLE,
            'is_participant': peserta_qs.exists(),
        })
        return context


class TugasLaporanPraktikumCreateView(PraktikumMahasiswaAccessMixin, CreateView):
    model = TugasLaporanPraktikum
    form_class = TugasLaporanPraktikumForm
    template_name = 'asleb/laporan_tugas_form.html'
    success_url = reverse_lazy('asleb:laporan_tugas_list')

    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role != ASISTEN_LAB_ROLE:
            messages.error(request, 'Tugas laporan praktikum hanya dapat dibuat oleh Asisten Lab aktif pada mata kuliah terkait.')
            return redirect('asleb:laporan_tugas_list')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['pengguna'] = self.request.current_pengguna
        return kwargs

    def form_valid(self, form):
        pengguna = self.request.current_pengguna
        active_asleb = get_active_asleb_for_matkul(pengguna, form.cleaned_data['matkul'])
        if pengguna.role == ASISTEN_LAB_ROLE and not active_asleb:
            form.add_error('matkul', 'Anda hanya dapat membuat tugas pada mata kuliah yang ditugaskan kepada Anda.')
            return self.form_invalid(form)
        form.instance.dibuat_oleh = pengguna
        # Biarkan kosong agar semua asisten aktif pada mata kuliah yang sama bisa memeriksa laporan.
        form.instance.asisten_pemeriksa = None
        response = super().form_valid(form)
        log_praktikum_activity(pengguna, 'tugas_laporan_dibuat', self.object.judul, self.object.matkul)
        notify_task_created(self.object, self.request)
        messages.success(self.request, 'Tugas laporan berhasil dibuat dan peserta terkait mendapat notifikasi.')
        return response


class PengumpulanLaporanPraktikumCreateView(FormView):
    form_class = PengumpulanLaporanPraktikumForm
    template_name = 'asleb/laporan_submit_form.html'
    success_url = reverse_lazy('asleb:laporan_tugas_list')

    def dispatch(self, request, *args, **kwargs):
        self.tugas = get_object_or_404(TugasLaporanPraktikum.objects.select_related('matkul'), pk=kwargs['pk'], aktif=True)
        self.peserta = get_participant_for_task(getattr(request, 'current_pengguna', None), self.tugas)
        if not self.peserta:
            messages.error(request, 'Anda bukan peserta pada mata kuliah tugas ini.')
            return redirect('asleb:laporan_tugas_list')
        if not self.tugas.is_open:
            messages.error(request, 'Periode pengumpulan laporan belum dibuka atau sudah ditutup.')
            return redirect('asleb:laporan_tugas_list')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tugas'] = self.tugas
        return kwargs

    def form_valid(self, form):
        latest = PengumpulanLaporanPraktikum.objects.filter(tugas=self.tugas, peserta=self.peserta).order_by('-versi').first()
        laporan = form.save(commit=False)
        laporan.tugas = self.tugas
        laporan.peserta = self.peserta
        laporan.versi = (latest.versi + 1) if latest else 1
        if latest and latest.status == PengumpulanLaporanPraktikum.STATUS_REVISI:
            laporan.status = PengumpulanLaporanPraktikum.STATUS_DIREVISI
        laporan.save()
        log_praktikum_activity(self.request.current_pengguna, 'laporan_dikumpulkan', self.tugas.judul, self.tugas.matkul, self.peserta)
        if self.tugas.asisten_pemeriksa and self.tugas.asisten_pemeriksa.email:
            reviewer = Pengguna.objects.filter(nim_nik=self.tugas.asisten_pemeriksa.nim).first()
            notify_pengguna(
                reviewer,
                f'laporan-submitted:{laporan.pk}',
                f'Laporan masuk: {self.tugas.judul}',
                f'{self.peserta.nama} mengumpulkan laporan {self.tugas.matkul}.',
                url=str(reverse_lazy('asleb:laporan_tugas_list')),
            )
        messages.success(self.request, 'Laporan berhasil dikumpulkan.')
        return redirect(self.success_url)


class ReviewLaporanPraktikumUpdateView(UpdateView):
    model = PengumpulanLaporanPraktikum
    form_class = ReviewLaporanPraktikumForm
    template_name = 'asleb/laporan_review_form.html'
    success_url = reverse_lazy('asleb:laporan_tugas_list')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        current_pengguna = getattr(request, 'current_pengguna', None)
        if not can_review_laporan(current_pengguna, self.object.tugas):
            messages.error(request, 'Anda tidak memiliki akses memeriksa laporan ini.')
            return redirect('asleb:laporan_tugas_list')
        if self.object.peserta.pengguna_id == getattr(current_pengguna, 'pk', None):
            messages.error(request, 'Asisten Lab tidak boleh menilai laporan miliknya sendiri.')
            return redirect('asleb:laporan_tugas_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.diperiksa_oleh = self.request.current_pengguna
        form.instance.diperiksa_pada = timezone.now()
        with transaction.atomic():
            response = super().form_valid(form)
            synced_result = sync_laporan_score_to_praktikum_result(self.object, self.request.current_pengguna)
        log_praktikum_activity(
            self.request.current_pengguna,
            'laporan_direview',
            f'{self.object.get_status_display()} - {self.object.tugas.judul}',
            self.object.tugas.matkul,
            self.object.peserta,
        )
        notify_pengguna(
            self.object.peserta.pengguna,
            f'laporan-reviewed:{self.object.pk}:{self.object.status}',
            f'Status laporan: {self.object.get_status_display()}',
            self.object.catatan_asisten or f'Laporan {self.object.tugas.judul} sudah diperbarui statusnya.',
            url=str(reverse_lazy('asleb:laporan_tugas_list')),
        )
        if synced_result:
            messages.success(self.request, 'Status laporan berhasil diperbarui dan nilai laporan otomatis masuk ke rekap nilai mahasiswa.')
        else:
            messages.success(self.request, 'Status laporan berhasil diperbarui.')
        return response


@require_POST
def delete_laporan_praktikum(request, pk):
    laporan = get_object_or_404(
        PengumpulanLaporanPraktikum.objects.select_related(
            'tugas',
            'tugas__matkul',
            'tugas__modul',
            'peserta',
            'peserta__pengguna',
        ),
        pk=pk,
    )
    pengguna = getattr(request, 'current_pengguna', None)
    if not can_review_laporan(pengguna, laporan.tugas):
        messages.error(request, 'Anda tidak memiliki akses untuk menghapus laporan ini.')
        return redirect('asleb:laporan_tugas_list')
    if laporan.peserta.pengguna_id == getattr(pengguna, 'pk', None):
        messages.error(request, 'Asisten Lab tidak dapat menghapus laporan miliknya sendiri melalui menu pemeriksaan.')
        return redirect('asleb:laporan_tugas_list')

    peserta = laporan.peserta
    tugas = laporan.tugas
    file_name = laporan.file_laporan.name if laporan.file_laporan else ''
    file_storage = laporan.file_laporan.storage if laporan.file_laporan else None

    with transaction.atomic():
        laporan.delete()

        if tugas.modul_id:
            hasil = HasilPraktikumMahasiswa.objects.filter(
                peserta=peserta,
                modul=tugas.modul,
            ).first()
            if hasil:
                laporan_pengganti = (
                    PengumpulanLaporanPraktikum.objects
                    .filter(
                        tugas__matkul=tugas.matkul,
                        tugas__modul=tugas.modul,
                        peserta=peserta,
                        nilai__isnull=False,
                    )
                    .select_related('diperiksa_oleh')
                    .order_by('-diperiksa_pada', '-dikumpulkan_pada', '-versi')
                    .first()
                )
                hasil.nilai_laporan = laporan_pengganti.nilai if laporan_pengganti else None
                hasil.dicatat_oleh = laporan_pengganti.diperiksa_oleh if laporan_pengganti else None
                hasil.catatan = laporan_pengganti.catatan_asisten[:250] if laporan_pengganti else ''
                if hasil.nilai_realtime is None and not laporan_pengganti:
                    hasil.nilai = None
                hasil.save(update_fields=[
                    'nilai_laporan',
                    'nilai',
                    'dicatat_oleh',
                    'catatan',
                    'diperbarui_pada',
                ])

        if file_name and file_storage:
            transaction.on_commit(lambda: file_storage.delete(file_name))

    log_praktikum_activity(
        pengguna,
        'laporan_dihapus',
        f'{tugas.judul} - {peserta.nama}',
        tugas.matkul,
        peserta,
    )
    notify_pengguna(
        peserta.pengguna,
        f'laporan-deleted:{pk}',
        f'Laporan dihapus: {tugas.judul}',
        'Laporan praktikum Anda dihapus oleh Asisten Lab. Silakan hubungi Asisten Lab jika memerlukan informasi lebih lanjut.',
        url=str(reverse_lazy('asleb:laporan_tugas_list')),
    )
    messages.success(request, f'Laporan {peserta.nama} berhasil dihapus.')
    return redirect('asleb:laporan_tugas_list')


def _serve_laporan_file(request, pk, *, inline=False):
    laporan = get_object_or_404(
        PengumpulanLaporanPraktikum.objects.select_related('tugas', 'peserta', 'peserta__pengguna'),
        pk=pk,
    )
    if not can_access_laporan(getattr(request, 'current_pengguna', None), laporan):
        messages.error(request, 'Anda tidak memiliki akses ke file laporan ini.')
        return redirect('asleb:laporan_tugas_list')
    if not laporan.file_laporan:
        messages.error(request, 'File laporan tidak ditemukan.')
        return redirect('asleb:laporan_tugas_list')
    filename = laporan.nama_file_asli or laporan.file_laporan.name.rsplit('/', 1)[-1] or 'laporan-praktikum'
    content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    response = FileResponse(laporan.file_laporan.open('rb'), content_type=content_type)
    disposition = 'inline' if inline and laporan.is_pdf else 'attachment'
    response['Content-Disposition'] = (
        content_disposition_header(disposition == 'attachment', filename)
        or f'{disposition}; filename="laporan-praktikum"'
    )
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, max-age=0, must-revalidate'
    if inline and laporan.is_pdf:
        response['X-Frame-Options'] = 'SAMEORIGIN'
    return response


def preview_laporan_praktikum(request, pk):
    laporan = get_object_or_404(
        PengumpulanLaporanPraktikum.objects.select_related('tugas', 'peserta', 'peserta__pengguna'),
        pk=pk,
    )
    if not can_access_laporan(getattr(request, 'current_pengguna', None), laporan):
        messages.error(request, 'Anda tidak memiliki akses ke file laporan ini.')
        return redirect('asleb:laporan_tugas_list')
    if not laporan.file_laporan:
        messages.error(request, 'File laporan tidak ditemukan.')
        return redirect('asleb:laporan_tugas_list')
    return render(request, 'asleb/laporan_preview.html', {'laporan': laporan})


@xframe_options_sameorigin
def preview_laporan_praktikum_file(request, pk):
    return _serve_laporan_file(request, pk, inline=True)


def download_laporan_praktikum(request, pk):
    return _serve_laporan_file(request, pk, inline=False)


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


def wants_json_response(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')


@require_POST
def delete_peserta_praktikum(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    if not can_manage_lab_operations(pengguna):
        messages.error(request, 'Hanya laboran yang dapat menghapus peserta praktikum.')
        return redirect('asleb:praktikum_mahasiswa_list')
    peserta = get_object_or_404(PesertaPraktikum.objects.select_related('matkul'), pk=pk)
    matkul_id = peserta.matkul_id
    result = delete_participant(peserta)
    if wants_json_response(request):
        return JsonResponse({
            'ok': True,
            'result': result,
            'message': 'Peserta dinonaktifkan agar riwayat nilai dan absensi tetap tersimpan.' if result == 'deactivated' else 'Peserta praktikum berhasil dihapus.',
            'participant_id': pk,
            'matkul_id': matkul_id,
        })
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
    affected_ids = []
    for peserta in peserta_queryset:
        affected_ids.append(peserta.pk)
        result = delete_participant(peserta)
        deleted += int(result == 'deleted')
        deactivated += int(result == 'deactivated')
    if wants_json_response(request):
        return JsonResponse({
            'ok': bool(deleted or deactivated),
            'deleted': deleted,
            'deactivated': deactivated,
            'affected_ids': affected_ids,
            'matkul_id': matkul_id,
            'message': f'{deleted} peserta dihapus dan {deactivated} peserta dinonaktifkan.' if deleted or deactivated else 'Pilih minimal satu peserta untuk dihapus.',
        }, status=200 if deleted or deactivated else 400)
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
    if wants_json_response(request):
        return JsonResponse({
            'ok': True,
            'deleted_all': True,
            'matkul_id': matkul.pk,
            'total': total,
            'message': f'{total} peserta praktikum berhasil dihapus dari daftar. Riwayat nilai tetap disimpan.',
        })
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
    matkul_labels = [str(matkul) for matkul in matkul_list]
    hasil_qs = (
        HasilPraktikumMahasiswa.objects
        .select_related('peserta', 'modul', 'modul__matkul', 'dicatat_oleh')
        .filter(Q(modul__matkul__in=matkul_qs) | Q(modul__isnull=True, matkul_label__in=matkul_labels))
        .order_by('modul__matkul__nama', 'modul__matkul__kelas', 'modul__nomor', 'peserta_nama')
    )
    if matkul_id:
        hasil_qs = hasil_qs.filter(modul__matkul_id=matkul_id)
        matkul_list = [item for item in matkul_list if str(item.pk) == matkul_id]
        if matkul_list:
            selected_label = str(matkul_list[0])
            hasil_qs = (
                HasilPraktikumMahasiswa.objects
                .select_related('peserta', 'modul', 'modul__matkul', 'dicatat_oleh')
                .filter(Q(modul__matkul_id=matkul_id) | Q(modul__isnull=True, matkul_label=selected_label))
                .order_by('modul__matkul__nama', 'modul__matkul__kelas', 'modul__nomor', 'peserta_nama')
            )
    hasil_list = list(hasil_qs)

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        used_names = set()
        for matkul in matkul_list:
            matkul_label = str(matkul)
            matkul_results = [
                hasil for hasil in hasil_list
                if (hasil.modul_id and hasil.modul.matkul_id == matkul.pk) or (not hasil.modul_id and hasil.matkul_label == matkul_label)
            ]
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
    module_numbers = {module.nomor for module in modules}
    archived_modules = []
    for hasil in hasil_list:
        if hasil.modul_id:
            module_number = hasil.modul.nomor
            module_title = hasil.modul.judul
        else:
            module_number = hasil.modul_nomor
            module_title = hasil.modul_judul
        if module_number and module_number not in module_numbers:
            archived_modules.append(type('ArchivedModule', (), {
                'nomor': module_number,
                'judul': module_title or f'Modul {module_number}',
            })())
            module_numbers.add(module_number)
    modules.extend(sorted(archived_modules, key=lambda item: item.nomor))
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
            module_number = hasil.modul.nomor if hasil.modul_id else hasil.modul_nomor
            if module_number:
                peserta_map[nim]['module_scores'][module_number] = score

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
            'letter': nilai_huruf(average) if average is not None else '-',
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
    headers.extend(['Total Nilai', 'Rata-rata Nilai', 'Nilai Huruf', 'Keterangan'])
    rows = [headers]
    for row in rekap['rows']:
        values = [row['no'], row['nim'], row['nama'], row['kelas'], row['matkul']]
        values.extend('' if score is None else f'{score:.2f}' for score in row['scores'])
        values.extend([
            '' if row['total'] is None else f'{row["total"]:.2f}',
            '' if row['average'] is None else f'{row["average"]:.2f}',
            row['letter'],
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
        'Nilai Huruf',
        'Catatan',
        'Dicatat Oleh',
    ]]
    for hasil in hasil_list:
        matkul = hasil.modul.matkul if hasil.modul_id else None
        nim = hasil.peserta.nim if hasil.peserta_id else hasil.peserta_nim
        matkul_label = hasil.matkul_label or (str(matkul) if matkul else 'Arsip mata kuliah')
        modul_number = hasil.modul.nomor if hasil.modul_id else hasil.modul_nomor
        modul_title = hasil.modul.judul if hasil.modul_id else hasil.modul_judul
        rows.append([
            matkul.nama if matkul else matkul_label,
            matkul.kelas if matkul else '',
            matkul.dosen if matkul else '',
            f'Modul {modul_number or "-"} - {modul_title or "Arsip modul"}',
            hasil.tanggal_praktikum.isoformat(),
            nim,
            hasil.peserta.nama if hasil.peserta_id else hasil.peserta_nama,
            hasil.get_status_absensi_display(),
            '' if hasil.nilai_realtime is None else str(hasil.nilai_realtime),
            '' if hasil.nilai_laporan is None else str(hasil.nilai_laporan),
            '' if hasil.hitung_nilai_rata_rata() is None else str(hasil.hitung_nilai_rata_rata()),
            '' if nim not in rata_rata_mahasiswa else str(rata_rata_mahasiswa[nim]),
            '' if nim not in rata_rata_mahasiswa else nilai_huruf(rata_rata_mahasiswa[nim]),
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


def _get_accessible_modul_praktikum(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    modul = get_object_or_404(ModulPraktikum.objects.select_related('matkul'), pk=pk)
    allowed = can_manage_lab_operations(pengguna)

    if pengguna and pengguna.role == ASISTEN_LAB_ROLE:
        asleb = (
            Asleb.objects.filter(nim=pengguna.nim_nik, status='aktif')
            .order_by('-diperbarui_pada', '-pk')
            .first()
        )
        allowed = bool(asleb and get_asleb_matkul(asleb) == modul.matkul)

    if not allowed:
        messages.error(request, 'Anda tidak memiliki akses ke modul praktikum ini.')
        return None

    return modul


def download_modul_praktikum(request, pk):
    modul = _get_accessible_modul_praktikum(request, pk)
    if not modul:
        return redirect('asleb:absensi_list')

    return FileResponse(
        modul.file.open('rb'),
        as_attachment=True,
        filename=modul.file.name.rsplit('/', 1)[-1],
    )


@xframe_options_sameorigin
def preview_modul_praktikum(request, pk):
    modul = _get_accessible_modul_praktikum(request, pk)
    if not modul:
        return redirect('asleb:absensi_list')

    filename = modul.file.name.rsplit('/', 1)[-1]
    content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    response = FileResponse(
        modul.file.open('rb'),
        as_attachment=False,
        filename=filename,
        content_type=content_type,
    )
    response['Content-Disposition'] = content_disposition_header(False, filename) or f'inline; filename="{filename.replace(chr(34), "")}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def _read_modul_pdf_bytes(modul):
    if not modul.is_pdf:
        raise Http404('Preview gambar hanya tersedia untuk file PDF.')
    with modul.file.open('rb') as file_obj:
        return file_obj.read()


def _get_modul_pdf_page_count(modul):
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(_read_modul_pdf_bytes(modul))
        return len(document)
    except Exception:
        return 0


def viewer_modul_praktikum(request, pk):
    modul = _get_accessible_modul_praktikum(request, pk)
    if not modul:
        return redirect('asleb:absensi_list')
    if not modul.is_pdf:
        return redirect('asleb:modul_preview', pk=modul.pk)

    return TemplateResponse(request, 'asleb/modul_pdf_viewer.html', {
        'modul': modul,
    })


def preview_modul_praktikum_page(request, pk, page):
    modul = _get_accessible_modul_praktikum(request, pk)
    if not modul:
        return redirect('asleb:absensi_list')

    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(_read_modul_pdf_bytes(modul))
        page_index = page - 1
        if page_index < 0 or page_index >= len(document):
            raise Http404('Halaman PDF tidak ditemukan.')
        pdf_page = document[page_index]
        bitmap = pdf_page.render(scale=2.2)
        image = bitmap.to_pil()
        output = BytesIO()
        image.save(output, format='PNG', optimize=True)
    except Http404:
        raise
    except Exception as exc:
        logger.warning('Gagal membuat preview modul %s halaman %s: %s', modul.pk, page, exc)
        raise Http404('Preview PDF tidak dapat dibuat.')

    response = HttpResponse(output.getvalue(), content_type='image/png')
    response['Cache-Control'] = 'private, max-age=300'
    return response


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
@transaction.atomic
def confirm_honor_transfer(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    if not can_manage_lab_operations(pengguna):
        messages.error(request, 'Hanya laboran yang bisa mengonfirmasi transfer honor.')
        return redirect('asleb:honor_list')

    asleb_id = get_object_or_404(HonorAsleb.objects.only('asleb_id'), pk=pk).asleb_id
    Asleb.objects.select_for_update().get(pk=asleb_id)
    honor = get_object_or_404(HonorAsleb.objects.select_for_update(), pk=pk)
    if not payment_eligible_honors(HonorAsleb.objects.filter(pk=honor.pk)).exists():
        messages.error(request, 'Honor sedang ditahan sampai proses penggantian aslab selesai.')
        return redirect('asleb:honor_list')
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
    with transaction.atomic():
        honor_qs = payment_eligible_honors(
            HonorAsleb.objects.select_for_update().select_related('asleb').exclude(status='dibayar')
        ).order_by('bulan', 'asleb__nama', 'pk')
        if selected_bulan:
            try:
                year, month = selected_bulan.split('-')
                honor_qs = honor_qs.filter(bulan__year=year, bulan__month=month)
            except ValueError:
                messages.error(request, 'Format bulan tidak valid.')
                return redirect('asleb:honor_list')
        assigned_count = rebalance_honor_transfers(honor_qs)

    if assigned_count:
        messages.success(request, f'{assigned_count} tugas TF honor berhasil dibagi rata otomatis ke laboran.')
    else:
        messages.info(request, 'Tidak ada honor belum dibayar yang perlu dibagi, atau belum ada akun laboran terverifikasi.')
    return redirect('asleb:honor_list')


def assign_unassigned_honor_transfers(honor_qs):
    assigned_count = 0
    for honor in payment_eligible_honors(honor_qs):
        laboran = honor.get_next_laboran_for_transfer()
        if not laboran:
            continue
        honor.assigned_laboran = laboran
        honor.save(update_fields=['assigned_laboran', 'level', 'jumlah', 'diperbarui_pada'])
        assigned_count += 1
    return assigned_count


def rebalance_honor_transfers(honor_qs):
    laboran_list = list(Pengguna.objects.filter(role=LABORAN_ROLE, is_verified=True).order_by('nama_pengguna', 'pk'))
    if not laboran_list:
        return 0

    honors_by_month = {}
    for honor in payment_eligible_honors(honor_qs):
        month_key = honor.bulan.replace(day=1)
        honors_by_month.setdefault(month_key, []).append(honor)

    changed_count = 0
    for honors in honors_by_month.values():
        for index, honor in enumerate(honors):
            target_laboran = laboran_list[index % len(laboran_list)]
            if honor.assigned_laboran_id == target_laboran.pk:
                continue
            honor.assigned_laboran = target_laboran
            honor.save(update_fields=['assigned_laboran', 'level', 'jumlah', 'diperbarui_pada'])
            changed_count += 1
    return changed_count


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
    total_pertemuan = get_total_honor_attendance_count(absensi.asleb, bulan)

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


def get_total_honor_attendance_count(asleb, bulan):
    web_absensi = AbsensiAsleb.objects.filter(
        asleb=asleb,
        tanggal_praktikum__year=bulan.year,
        tanggal_praktikum__month=bulan.month,
    )
    mobile_absensi = AbsensiMasukAsleb.objects.filter(
        asleb=asleb,
        tanggal_absensi__year=bulan.year,
        tanggal_absensi__month=bulan.month,
    )

    web_keys = set(web_absensi.exclude(jadwal__isnull=True).values_list('jadwal_id', 'tanggal_praktikum'))
    mobile_count = 0
    for attendance in mobile_absensi.values('jadwal_id', 'tanggal_absensi'):
        key = (attendance['jadwal_id'], attendance['tanggal_absensi'])
        if attendance['jadwal_id'] and key in web_keys:
            continue
        mobile_count += 1

    return web_absensi.count() + mobile_count


def sync_honor_from_mobile_absensi(absensi_masuk):
    bulan = absensi_masuk.tanggal_absensi.replace(day=1)
    honor, _ = HonorAsleb.objects.get_or_create(
        asleb=absensi_masuk.asleb,
        bulan=bulan,
        defaults={
            'jumlah_praktikum': 1,
            'pic_transfer': '',
            'status': 'diproses',
        },
    )
    honor.jumlah_praktikum = max(honor.jumlah_praktikum, 1)
    honor.total_pertemuan = get_total_honor_attendance_count(absensi_masuk.asleb, bulan)
    if honor.status == 'draft':
        honor.status = 'diproses'
    honor.save()
    return honor
