from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.views import PostOnlyDeleteMixin

from .forms import AbsensiAslebForm, AslebForm, HonorAslebForm, KonfirmasiTransferHonorForm
from .models import AbsensiAsleb, Asleb, HonorAsleb, PengaturanAbsensiAsleb


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
        queryset = HonorAsleb.objects.select_related('asleb')
        search = self.request.GET.get('q', '').strip()
        bulan = self.request.GET.get('bulan', '').strip()
        status = self.request.GET.get('status', '').strip()

        if search:
            queryset = queryset.filter(
                Q(asleb__nama__icontains=search) |
                Q(asleb__nim__icontains=search) |
                Q(asleb__matkul__icontains=search) |
                Q(pic_transfer__icontains=search)
            )

        if bulan:
            queryset = queryset.filter(bulan__month=bulan.split('-')[1], bulan__year=bulan.split('-')[0])

        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bulan_ini = timezone.localdate().replace(day=1)
        selected_bulan = self.request.GET.get('bulan', bulan_ini.strftime('%Y-%m'))
        total_honor = self.get_queryset().aggregate(total=Sum('jumlah'))['total'] or 0

        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_bulan'] = selected_bulan
        context['selected_status'] = self.request.GET.get('status', '').strip()
        context['status_choices'] = HonorAsleb.STATUS_CHOICES
        context['total_honor'] = f'Rp {total_honor:,.0f}'.replace(',', '.')
        context['formula_note'] = 'Total Honor = min(7 x Total Pertemuan, 60) x Honor/Jam. Level otomatis: periode asleb ke-1 dan ke-2 Junior Rp7.000, mulai ke-3 Senior Rp8.000.'
        return context


class HonorAslebCreateView(CreateView):
    model = HonorAsleb
    form_class = HonorAslebForm
    template_name = 'asleb/honor_form.html'
    success_url = reverse_lazy('asleb:honor_list')


class HonorAslebUpdateView(UpdateView):
    model = HonorAsleb
    form_class = HonorAslebForm
    template_name = 'asleb/honor_form.html'
    success_url = reverse_lazy('asleb:honor_list')


class HonorAslebDeleteView(PostOnlyDeleteMixin, DeleteView):
    model = HonorAsleb
    template_name = 'asleb/honor_confirm_delete.html'
    context_object_name = 'honor'
    success_url = reverse_lazy('asleb:honor_list')


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
            messages.error(request, 'Data Asleb untuk akun ini belum ditemukan.')
            return redirect('dashboard:home')

        if not PengaturanAbsensiAsleb.get_solo().dibuka:
            messages.warning(request, 'Absensi asleb sedang ditutup oleh admin/laboran.')
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
    messages.success(request, f'Absensi asleb berhasil {status}.')
    return redirect('asleb:absensi_list')


@require_POST
def confirm_honor_transfer(request, pk):
    pengguna = getattr(request, 'current_pengguna', None)
    if not pengguna or pengguna.role not in {'admin', 'laboran'}:
        messages.error(request, 'Hanya admin dan laboran yang bisa mengonfirmasi transfer honor.')
        return redirect('asleb:honor_list')

    honor = get_object_or_404(HonorAsleb, pk=pk)
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
