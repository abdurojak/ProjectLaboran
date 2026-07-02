import logging

from django.contrib import messages
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q, Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.text import slugify
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from apps.core.views import PostOnlyDeleteMixin
from apps.jadwal.models import JadwalPraktikum
from apps.pengguna.models import Pengguna

from .forms import (
    AbsensiAslebForm,
    AslebForm,
    ENABLE_CAMERA_LOCATION_CAPTURE,
    HonorAslebForm,
    KonfirmasiTransferHonorForm,
    HasilPraktikumMahasiswaForm,
    ModulPraktikumForm,
    PesertaPraktikumBulkForm,
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
        if not pengguna or pengguna.role != 'admin':
            messages.error(request, 'Hanya admin yang bisa mengelola rekap honorarium.')
            return redirect('asleb:honor_list')
        return super().dispatch(request, *args, **kwargs)


class AslebListView(ListView):
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
        context['can_end_asleb'] = bool(pengguna and pengguna.role in {'admin', 'laboran'})
        return context


@require_POST
@transaction.atomic
def end_asleb_membership(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    if not pengguna or pengguna.role not in {'admin', 'laboran'}:
        messages.error(request, 'Hanya admin dan laboran yang dapat mengakhiri masa tugas aslab.')
        return redirect('asleb:asleb_list')

    asleb = get_object_or_404(Asleb, pk=pk)
    Asleb.objects.filter(nim=asleb.nim, status='aktif').update(status='nonaktif')
    akun = Pengguna.objects.filter(nim_nik=asleb.nim).first()
    if akun and akun.role == 'asisten_lab':
        akun.role = 'mahasiswa'
        akun.save(update_fields=['role', 'diperbarui_pada'])

    messages.success(request, f'Masa tugas {asleb.nama} diakhiri. Role akun kini menjadi Mahasiswa.')
    return redirect('asleb:asleb_list')


class AslebDetailView(DetailView):
    model = Asleb
    template_name = 'asleb/asleb_detail.html'
    context_object_name = 'asleb'


class AslebCreateView(CreateView):
    model = Asleb
    form_class = AslebForm
    template_name = 'asleb/asleb_form.html'
    success_url = reverse_lazy('asleb:asleb_list')


class AslebUpdateView(UpdateView):
    model = Asleb
    form_class = AslebForm
    template_name = 'asleb/asleb_form.html'
    success_url = reverse_lazy('asleb:asleb_list')


class AslebDeleteView(PostOnlyDeleteMixin, DeleteView):
    model = Asleb
    template_name = 'asleb/asleb_confirm_delete.html'
    context_object_name = 'asleb'
    success_url = reverse_lazy('asleb:asleb_list')


class HonorAslebListView(ListView):
    model = HonorAsleb
    template_name = 'asleb/honor_list.html'
    context_object_name = 'honor_list'

    def get_queryset(self):
        queryset = HonorAsleb.objects.select_related('asleb', 'assigned_laboran')
        pengguna = getattr(self.request, 'current_pengguna', None)
        search = self.request.GET.get('q', '').strip()
        bulan = self.request.GET.get('bulan', '').strip()
        status = self.request.GET.get('status', '').strip()

        if pengguna and pengguna.role == 'laboran':
            queryset = queryset.filter(assigned_laboran=pengguna)

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
        if pengguna and pengguna.role == 'laboran':
            base_honor_qs = base_honor_qs.filter(assigned_laboran=pengguna)

        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_bulan'] = selected_bulan
        context['selected_status'] = self.request.GET.get('status', '').strip()
        context['status_choices'] = HonorAsleb.STATUS_CHOICES
        context['total_honor'] = f'Rp {total_honor:,.0f}'.replace(',', '.')
        context['laboran_count'] = Pengguna.objects.filter(role='laboran', is_verified=True).count()
        context['unassigned_honor_count'] = base_honor_qs.filter(assigned_laboran__isnull=True).count()
        context['is_admin'] = bool(pengguna and pengguna.role == 'admin')
        context['is_laboran'] = bool(pengguna and pengguna.role == 'laboran')
        context['formula_note'] = 'Total Honor = min(7 x Total Pertemuan, 60) x Honor/Jam. Level otomatis: periode aslab ke-1 dan ke-2 Junior Rp7.000, mulai ke-3 Senior Rp8.000.'
        return context


class HonorAslebCreateView(HonorAdminRequiredMixin, CreateView):
    model = HonorAsleb
    form_class = HonorAslebForm
    template_name = 'asleb/honor_form.html'
    success_url = reverse_lazy('asleb:honor_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return kwargs


class HonorAslebUpdateView(UpdateView):
    model = HonorAsleb
    form_class = HonorAslebForm
    template_name = 'asleb/honor_form.html'
    success_url = reverse_lazy('asleb:honor_list')

    def get_queryset(self):
        queryset = super().get_queryset()
        pengguna = getattr(self.request, 'current_pengguna', None)
        if pengguna and pengguna.role == 'laboran':
            return queryset.filter(assigned_laboran=pengguna)
        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return kwargs


class HonorAslebDeleteView(HonorAdminRequiredMixin, PostOnlyDeleteMixin, DeleteView):
    model = HonorAsleb
    template_name = 'asleb/honor_confirm_delete.html'
    context_object_name = 'honor'
    success_url = reverse_lazy('asleb:honor_list')


class SuratHonorAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        cleanup_expired_surat_honor()
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role not in {'admin', 'laboran'}:
            messages.error(request, 'Hanya admin dan laboran yang bisa mengakses arsip surat honor.')
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
    if not pengguna or pengguna.role not in {'admin', 'laboran'}:
        messages.error(request, 'Hanya admin dan laboran yang bisa mengunduh surat honor.')
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

        if pengguna and pengguna.role == 'asisten_lab':
            queryset = queryset.filter(asleb__nim=pengguna.nim_nik)

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
        context['is_asisten_lab'] = bool(pengguna and pengguna.role == 'asisten_lab')
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
        context['can_manage_modul'] = bool(pengguna and pengguna.role in {'admin', 'laboran'})
        return context

    def get_modul_list(self, pengguna, asleb_profile):
        queryset = ModulPraktikum.objects.select_related('matkul', 'diunggah_oleh')
        if pengguna and pengguna.role == 'asisten_lab':
            matkul = get_asleb_matkul(asleb_profile) if asleb_profile else None
            return queryset.filter(matkul=matkul) if matkul else queryset.none()
        return queryset

    def get_asleb_profile(self, pengguna):
        if not pengguna or pengguna.role != 'asisten_lab':
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

        if not pengguna or pengguna.role != 'asisten_lab':
            messages.error(request, 'Absensi hanya bisa diisi oleh role Asisten Lab.')
            return redirect('dashboard:home')

        if not self.asleb:
            messages.error(request, 'Data Aslab untuk akun ini belum ditemukan.')
            return redirect('dashboard:home')

        if not PengaturanAbsensiAsleb.get_solo().dibuka:
            messages.warning(request, 'Absensi aslab sedang ditutup oleh admin/laboran.')
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
        if not pengguna or pengguna.role not in {'admin', 'laboran'}:
            messages.error(request, 'Hanya laboran dan admin yang bisa mengelola modul praktikum.')
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
    from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb

    queryset = MataKuliahAsleb.objects.filter(aktif=True)
    if not pengguna:
        return queryset.none()
    if pengguna.role in {'admin', 'laboran'}:
        return queryset
    if pengguna.role != 'asisten_lab':
        return queryset.none()

    matkul_ids = PendaftaranAsleb.objects.filter(
        nim=pengguna.nim_nik,
        status__in=['diterima', 'digenerate'],
    ).values_list('matkul_id', flat=True)
    if matkul_ids:
        return queryset.filter(pk__in=matkul_ids)

    asleb = Asleb.objects.filter(nim=pengguna.nim_nik).first()
    fallback = get_asleb_matkul(asleb) if asleb else None
    return queryset.filter(pk=fallback.pk) if fallback else queryset.none()


class PraktikumMahasiswaAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role not in {'admin', 'laboran', 'asisten_lab'}:
            messages.error(request, 'Anda tidak memiliki akses ke nilai dan absensi mahasiswa.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)


class PesertaPraktikumManageMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role not in {'admin', 'laboran'}:
            messages.error(request, 'Hanya admin dan laboran yang dapat mengelola peserta praktikum.')
            return redirect('asleb:praktikum_mahasiswa_list')
        return super().dispatch(request, *args, **kwargs)


class PraktikumMahasiswaListView(PraktikumMahasiswaAccessMixin, TemplateView):
    template_name = 'asleb/praktikum_mahasiswa_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pengguna = self.request.current_pengguna
        matkul_list = list(
            get_praktikum_matkul_queryset(pengguna)
            .prefetch_related('modul_praktikum')
            .order_by('nama', 'kelas')
        )
        for matkul in matkul_list:
            matkul.jumlah_peserta = matkul.peserta_praktikum.filter(aktif=True).count()
            matkul.modul_tersedia = list(matkul.modul_praktikum.all())

        selected_id = self.request.GET.get('matkul', '').strip()
        selected_matkul = next((item for item in matkul_list if str(item.pk) == selected_id), None)
        if not selected_matkul and len(matkul_list) == 1:
            selected_matkul = matkul_list[0]

        context.update({
            'matkul_list': matkul_list,
            'selected_matkul': selected_matkul,
            'peserta_list': (
                selected_matkul.peserta_praktikum.select_related('pengguna').all()
                if selected_matkul else PesertaPraktikum.objects.none()
            ),
            'can_manage_peserta': pengguna.role in {'admin', 'laboran'},
            'is_asisten_lab': pengguna.role == 'asisten_lab',
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
            for row in form.cleaned_data['daftar_mahasiswa']:
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


@require_POST
def delete_peserta_praktikum(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    if not pengguna or pengguna.role not in {'admin', 'laboran'}:
        messages.error(request, 'Hanya admin dan laboran yang dapat menghapus peserta praktikum.')
        return redirect('asleb:praktikum_mahasiswa_list')
    peserta = get_object_or_404(PesertaPraktikum.objects.select_related('matkul'), pk=pk)
    matkul_id = peserta.matkul_id
    if peserta.hasil_praktikum.exists():
        peserta.aktif = False
        peserta.save(update_fields=['aktif', 'diperbarui_pada'])
        messages.success(request, 'Peserta dinonaktifkan agar riwayat nilai dan absensi tetap tersimpan.')
    else:
        peserta.delete()
        messages.success(request, 'Peserta praktikum berhasil dihapus.')
    return redirect(f'{reverse_lazy("asleb:praktikum_mahasiswa_list")}?matkul={matkul_id}')


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
            'is_asisten_lab': self.request.current_pengguna.role == 'asisten_lab',
        })
        return context


def download_modul_praktikum(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    modul = get_object_or_404(ModulPraktikum.objects.select_related('matkul'), pk=pk)
    allowed = bool(pengguna and pengguna.role in {'admin', 'laboran'})

    if pengguna and pengguna.role == 'asisten_lab':
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
    if not pengguna or pengguna.role not in {'admin', 'laboran'}:
        messages.error(request, 'Hanya admin dan laboran yang bisa membuka atau menutup absensi.')
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
    if not pengguna or pengguna.role not in {'admin', 'laboran'}:
        messages.error(request, 'Hanya admin dan laboran yang bisa mengonfirmasi transfer honor.')
        return redirect('asleb:honor_list')

    honor = get_object_or_404(HonorAsleb, pk=pk)
    if pengguna.role == 'laboran' and honor.assigned_laboran_id != pengguna.pk:
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
    messages.success(request, f'Honor {honor.asleb.nama} berhasil dikonfirmasi sudah ditransfer.')
    return redirect('asleb:honor_list')


@require_POST
def auto_assign_honor_transfers(request):
    pengguna = getattr(request, 'current_pengguna', None)
    if not pengguna or pengguna.role != 'admin':
        messages.error(request, 'Hanya admin yang bisa membagi tugas TF otomatis.')
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
