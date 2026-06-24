from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.asleb.models import Asleb
from apps.core.views import PostOnlyDeleteMixin
from apps.pengguna.models import Pengguna

from .forms import MataKuliahAslebForm, PendaftaranAslebForm, PendaftaranAslebPublicForm
from .models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb
from .utils import get_public_registration_url


class PendaftaranAslebListView(ListView):
    model = PendaftaranAsleb
    template_name = 'pendaftaran_asleb/pendaftaran_list.html'
    context_object_name = 'pendaftaran_list'

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
                Q(matkul__kode__icontains=search) |
                Q(matkul__nama__icontains=search) |
                Q(matkul__dosen__icontains=search) |
                Q(matkul__kelas__icontains=search)
            )

        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_status'] = self.request.GET.get('status', '').strip()
        context['status_choices'] = PendaftaranAsleb.STATUS_CHOICES
        context['public_registration_url'] = get_public_registration_url()
        context['pengaturan_pendaftaran'] = PengaturanPendaftaranAsleb.get_solo()
        return context


class PendaftaranAslebDetailView(DetailView):
    model = PendaftaranAsleb
    template_name = 'pendaftaran_asleb/pendaftaran_detail.html'
    context_object_name = 'pendaftaran'


class PendaftaranAslebCreateView(CreateView):
    model = PendaftaranAsleb
    form_class = PendaftaranAslebForm
    template_name = 'pendaftaran_asleb/pendaftaran_form.html'
    success_url = reverse_lazy('pendaftaran_asleb:pendaftaran_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['files'] = self.request.FILES or None
        return kwargs


class PendaftaranAslebUpdateView(UpdateView):
    model = PendaftaranAsleb
    form_class = PendaftaranAslebForm
    template_name = 'pendaftaran_asleb/pendaftaran_form.html'
    success_url = reverse_lazy('pendaftaran_asleb:pendaftaran_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['files'] = self.request.FILES or None
        return kwargs


class PendaftaranAslebDeleteView(PostOnlyDeleteMixin, DeleteView):
    model = PendaftaranAsleb
    template_name = 'pendaftaran_asleb/pendaftaran_confirm_delete.html'
    context_object_name = 'pendaftaran'
    success_url = reverse_lazy('pendaftaran_asleb:pendaftaran_list')


class PendaftaranAslebPublicCreateView(CreateView):
    model = PendaftaranAsleb
    form_class = PendaftaranAslebPublicForm
    template_name = 'pendaftaran_asleb/pendaftaran_public_form.html'
    success_url = reverse_lazy('pendaftaran_asleb:pendaftaran_success')

    def dispatch(self, request, *args, **kwargs):
        if not PengaturanPendaftaranAsleb.get_solo().dibuka:
            return render(request, 'pendaftaran_asleb/pendaftaran_closed.html')

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['files'] = self.request.FILES or None
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None) or get_session_pengguna(self.request)
        return kwargs


class PendaftaranAslebSuccessView(ListView):
    model = PendaftaranAsleb
    template_name = 'pendaftaran_asleb/pendaftaran_success.html'
    context_object_name = 'pendaftaran_list'

    def get_queryset(self):
        return PendaftaranAsleb.objects.none()


@require_POST
def accept_pendaftaran(request, pk):
    pendaftaran = get_object_or_404(PendaftaranAsleb, pk=pk)
    pendaftaran.status = 'diterima'
    pendaftaran.save(update_fields=['status', 'diperbarui_pada'])
    promote_pengguna_to_asisten_lab(pendaftaran)
    messages.success(request, 'Pendaftaran asleb ditandai diterima.')
    return redirect('pendaftaran_asleb:pendaftaran_list')


@require_POST
def reject_pendaftaran(request, pk):
    pendaftaran = get_object_or_404(PendaftaranAsleb, pk=pk)
    pendaftaran.status = 'ditolak'
    pendaftaran.save(update_fields=['status', 'diperbarui_pada'])
    messages.warning(request, 'Pendaftaran asleb ditandai ditolak.')
    return redirect('pendaftaran_asleb:pendaftaran_list')


@require_POST
def generate_asleb(request, pk):
    pendaftaran = get_object_or_404(PendaftaranAsleb, pk=pk)

    if pendaftaran.status != 'diterima':
        messages.error(request, 'Hanya pendaftaran yang diterima yang bisa digenerate ke Data Asleb.')
        return redirect('pendaftaran_asleb:pendaftaran_list')

    create_or_update_asleb_from_pendaftaran(pendaftaran)
    pendaftaran.status = 'digenerate'
    pendaftaran.save(update_fields=['status', 'diperbarui_pada'])
    messages.success(request, 'Pendaftaran berhasil digenerate ke Data Asleb.')
    return redirect('asleb:asleb_list')


@require_POST
def generate_all_accepted_asleb(request):
    accepted_registrations = PendaftaranAsleb.objects.filter(status='diterima')
    generated_count = 0

    for pendaftaran in accepted_registrations:
        create_or_update_asleb_from_pendaftaran(pendaftaran)
        pendaftaran.status = 'digenerate'
        pendaftaran.save(update_fields=['status', 'diperbarui_pada'])
        generated_count += 1

    if generated_count:
        messages.success(request, f'{generated_count} pendaftar diterima berhasil digenerate ke Data Asleb.')
    else:
        messages.warning(request, 'Belum ada pendaftar berstatus diterima untuk digenerate.')

    return redirect('asleb:asleb_list' if generated_count else 'pendaftaran_asleb:pendaftaran_list')


@require_POST
def toggle_pendaftaran_status(request):
    pengaturan = PengaturanPendaftaranAsleb.get_solo()
    pengaturan.dibuka = not pengaturan.dibuka
    pengaturan.save(update_fields=['dibuka', 'diperbarui_pada'])

    status = 'dibuka' if pengaturan.dibuka else 'ditutup'
    notified_count = notify_pendaftaran_dibuka() if pengaturan.dibuka else 0

    if notified_count:
        messages.success(request, f'Pendaftaran asleb berhasil {status}. Notifikasi email dikirim ke {notified_count} akun.')
    else:
        messages.success(request, f'Pendaftaran asleb berhasil {status}.')
    return redirect('pendaftaran_asleb:pendaftaran_list')


def get_session_pengguna(request):
    pengguna_id = request.session.get('pengguna_id')
    if not pengguna_id:
        return None

    return Pengguna.objects.filter(pk=pengguna_id).first()


def notify_pendaftaran_dibuka():
    recipients = list(
        Pengguna.objects.filter(
            role__in=['mahasiswa', 'asisten_lab'],
            is_verified=True,
        ).exclude(email='').values_list('email', flat=True).distinct()
    )

    if not recipients:
        return 0

    registration_url = get_public_registration_url()
    sent_count = 0

    for email in recipients:
        sent = send_mail(
            subject='Pendaftaran Asleb Project Laboran Dibuka',
            message=(
                'Pendaftaran asisten laboratorium sudah dibuka.\n\n'
                f'Silakan daftar melalui link berikut:\n{registration_url}\n\n'
                'Jika Anda membuka link dalam kondisi sudah login, nama dan NIM akan otomatis terisi dari akun.'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[email],
            fail_silently=True,
        )
        sent_count += sent

    return sent_count


def create_or_update_asleb_from_pendaftaran(pendaftaran):
    Asleb.objects.update_or_create(
        nim=pendaftaran.nim,
        defaults={
            'nama': pendaftaran.nama,
            'no_hp': pendaftaran.no_hp,
            'email': pendaftaran.email,
            'program_studi': pendaftaran.program_studi,
            'semester': pendaftaran.semester,
            'matkul': str(pendaftaran.matkul),
            'status': 'aktif',
            'tanggal_bergabung': timezone.localdate(),
            'catatan': f'Digenerate dari pendaftaran asleb tanggal {pendaftaran.tanggal_daftar:%d-%m-%Y}.',
        },
    )
    promote_pengguna_to_asisten_lab(pendaftaran)


def promote_pengguna_to_asisten_lab(pendaftaran):
    Pengguna.objects.filter(
        nim_nik=pendaftaran.nim,
        role='mahasiswa',
    ).update(role='asisten_lab')


class MataKuliahAslebListView(ListView):
    model = MataKuliahAsleb
    template_name = 'pendaftaran_asleb/matkul_list.html'
    context_object_name = 'matkul_list'


class MataKuliahAslebCreateView(CreateView):
    model = MataKuliahAsleb
    form_class = MataKuliahAslebForm
    template_name = 'pendaftaran_asleb/matkul_form.html'
    success_url = reverse_lazy('pendaftaran_asleb:matkul_list')


class MataKuliahAslebUpdateView(UpdateView):
    model = MataKuliahAsleb
    form_class = MataKuliahAslebForm
    template_name = 'pendaftaran_asleb/matkul_form.html'
    success_url = reverse_lazy('pendaftaran_asleb:matkul_list')


class MataKuliahAslebDeleteView(PostOnlyDeleteMixin, DeleteView):
    model = MataKuliahAsleb
    template_name = 'pendaftaran_asleb/matkul_confirm_delete.html'
    context_object_name = 'matkul'
    success_url = reverse_lazy('pendaftaran_asleb:matkul_list')
