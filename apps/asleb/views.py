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
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView

from apps.core.views import PostOnlyDeleteMixin
from apps.pengguna.models import Pengguna

from .forms import AbsensiAslebForm, AslebForm, HonorAslebForm, KonfirmasiTransferHonorForm, SuratHonorAslebGenerateForm
from .models import AbsensiAsleb, Asleb, HonorAsleb, PengaturanAbsensiAsleb, SuratHonorAsleb
from .surat_honor import generate_surat_honor_pdf, month_year_label


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
        return context


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
        return context

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

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['files'] = self.request.FILES or None
        kwargs['asleb'] = self.asleb
        return kwargs

    def form_valid(self, form):
        form.instance.asleb = self.asleb
        response = super().form_valid(form)
        sync_honor_from_absensi(self.object)
        messages.success(self.request, f'Absensi Modul {self.object.modul} berhasil disimpan.')
        return response


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
