from django.contrib import messages
from django.conf import settings
<<<<<<< HEAD
=======
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
<<<<<<< HEAD
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
=======
from django.utils.text import get_valid_filename
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View
import uuid
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271

from apps.asleb.models import Asleb
from apps.core.views import PostOnlyDeleteMixin
from apps.pengguna.models import Pengguna

<<<<<<< HEAD
from .forms import MataKuliahAslebForm, PendaftaranAslebForm, PendaftaranAslebPublicForm
from .models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb
from .utils import get_public_registration_url
=======
from .forms import (
    MataKuliahAslebForm,
    PendaftaranAslebForm,
    PendaftaranAslebPublicForm,
    PublicBerkasPendaftaranForm,
    PublicPilihMatkulForm,
    PublicTranskripForm,
    decode_signature_data,
)
from .models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb
from .utils import extract_grade_from_transcript, get_public_registration_url, is_passing_grade


WIZARD_SESSION_KEY = 'pendaftaran_asleb_wizard'
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271


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


<<<<<<< HEAD
class PendaftaranAslebPublicCreateView(CreateView):
    model = PendaftaranAsleb
    form_class = PendaftaranAslebPublicForm
    template_name = 'pendaftaran_asleb/pendaftaran_public_form.html'
    success_url = reverse_lazy('pendaftaran_asleb:pendaftaran_success')
=======
class PendaftaranAslebPublicCreateView(View):
    template_name = 'pendaftaran_asleb/pendaftaran_public_form.html'
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271

    def dispatch(self, request, *args, **kwargs):
        if not PengaturanPendaftaranAsleb.get_solo().dibuka:
            return render(request, 'pendaftaran_asleb/pendaftaran_closed.html')

        return super().dispatch(request, *args, **kwargs)

<<<<<<< HEAD
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['files'] = self.request.FILES or None
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None) or get_session_pengguna(self.request)
        return kwargs
=======
    def get(self, request, *args, **kwargs):
        if request.GET.get('reset') == '1':
            self.clear_wizard(request)
        return self.render_current_step(request)

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', '')
        if action == 'reset':
            self.clear_wizard(request)
            return redirect('pendaftaran_asleb:pendaftaran_public')
        if action == 'back':
            return self.go_back(request)

        wizard = self.get_wizard(request)
        step = wizard.get('step', 'matkul')
        if step == 'matkul':
            return self.handle_matkul_step(request)
        if step == 'transkrip':
            return self.handle_transkrip_step(request)
        if step == 'berkas':
            return self.handle_berkas_step(request)
        return self.render_current_step(request)

    def get_wizard(self, request):
        wizard = request.session.get(WIZARD_SESSION_KEY) or {'step': 'matkul'}
        request.session[WIZARD_SESSION_KEY] = wizard
        return wizard

    def clear_wizard(self, request):
        wizard = request.session.pop(WIZARD_SESSION_KEY, None)
        if wizard and wizard.get('transkrip_path'):
            default_storage.delete(wizard['transkrip_path'])
        request.session.modified = True

    def go_back(self, request):
        wizard = self.get_wizard(request)
        if wizard.get('step') == 'berkas':
            wizard['step'] = 'transkrip'
        elif wizard.get('step') == 'transkrip':
            wizard['step'] = 'matkul'
        request.session.modified = True
        return redirect('pendaftaran_asleb:pendaftaran_public')

    def handle_matkul_step(self, request):
        form = PublicPilihMatkulForm(request.POST)
        if not form.is_valid():
            return self.render_current_step(request, matkul_form=form)

        wizard = self.get_wizard(request)
        old_transkrip_path = wizard.get('transkrip_path')
        if old_transkrip_path:
            default_storage.delete(old_transkrip_path)
        wizard.clear()
        wizard.update({
            'step': 'transkrip',
            'matkul_id': form.cleaned_data['matkul'].pk,
        })
        request.session.modified = True
        return redirect('pendaftaran_asleb:pendaftaran_public')

    def handle_transkrip_step(self, request):
        wizard = self.get_wizard(request)
        matkul = self.get_selected_matkul(wizard)
        if not matkul:
            wizard['step'] = 'matkul'
            request.session.modified = True
            return redirect('pendaftaran_asleb:pendaftaran_public')

        form = PublicTranskripForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_current_step(request, transkrip_form=form)

        transkrip = form.cleaned_data['transkrip']
        detected_grade = extract_grade_from_transcript(transkrip, matkul) or 'tidak_terbaca'
        transkrip.seek(0)
        old_transkrip_path = wizard.get('transkrip_path')
        if old_transkrip_path:
            default_storage.delete(old_transkrip_path)
        safe_name = get_valid_filename(transkrip.name)
        temp_path = default_storage.save(
            f'pendaftaran_asleb/transkrip_tmp/{uuid.uuid4().hex}-{safe_name}',
            transkrip,
        )
        wizard.update({
            'step': 'berkas' if is_passing_grade(detected_grade) else 'transkrip',
            'transkrip_path': temp_path,
            'transkrip_name': safe_name,
            'nilai_transkrip': detected_grade,
            'nilai_lolos': is_passing_grade(detected_grade),
        })
        request.session.modified = True
        if is_passing_grade(detected_grade):
            messages.success(request, f'Nilai {detected_grade} terbaca untuk {matkul.nama}. Anda bisa lanjut mengisi berkas.')
        else:
            messages.error(request, 'Nilai mata kuliah belum memenuhi minimal C atau tidak terbaca. Upload transkrip yang benar untuk melanjutkan.')
        return redirect('pendaftaran_asleb:pendaftaran_public')

    def handle_berkas_step(self, request):
        wizard = self.get_wizard(request)
        matkul = self.get_selected_matkul(wizard)
        if not matkul or not wizard.get('nilai_lolos') or not wizard.get('transkrip_path'):
            wizard['step'] = 'matkul'
            request.session.modified = True
            return redirect('pendaftaran_asleb:pendaftaran_public')

        current_pengguna = getattr(request, 'current_pengguna', None) or get_session_pengguna(request)
        form = PublicBerkasPendaftaranForm(request.POST, request.FILES, current_pengguna=current_pengguna)
        if not form.is_valid():
            return self.render_current_step(request, berkas_form=form)

        signature_file = decode_signature_data(form.cleaned_data.get('signature_data'))
        with default_storage.open(wizard['transkrip_path'], 'rb') as transkrip_file:
            transkrip_content = ContentFile(transkrip_file.read(), name=wizard.get('transkrip_name') or 'transkrip.pdf')

        pendaftaran = PendaftaranAsleb(
            nama=form.cleaned_data['nama'],
            nim=form.cleaned_data['nim'],
            no_hp=form.cleaned_data['no_hp'],
            email=form.cleaned_data.get('email', ''),
            program_studi=form.cleaned_data['program_studi'],
            semester=form.cleaned_data['semester'],
            matkul=matkul,
            cv=form.cleaned_data['cv'],
            transkrip=transkrip_content,
            tanda_tangan=signature_file,
            metode_rekening=form.cleaned_data['metode_rekening'],
            rekening=form.cleaned_data['rekening'],
            nilai_transkrip=wizard['nilai_transkrip'],
            skor_nilai=PendaftaranAsleb.grade_to_score(wizard['nilai_transkrip']),
            alasan=form.cleaned_data.get('alasan', ''),
            status='diajukan',
        )
        pendaftaran.save()
        default_storage.delete(wizard['transkrip_path'])
        request.session.pop(WIZARD_SESSION_KEY, None)
        request.session.modified = True
        messages.success(request, 'Pendaftaran aslab berhasil dikirim.')
        return redirect('pendaftaran_asleb:pendaftaran_success')

    def render_current_step(self, request, **forms):
        wizard = self.get_wizard(request)
        step = wizard.get('step', 'matkul')
        matkul = self.get_selected_matkul(wizard)
        current_pengguna = getattr(request, 'current_pengguna', None) or get_session_pengguna(request)

        context = {
            'step': step,
            'selected_matkul': matkul,
            'nilai_transkrip': wizard.get('nilai_transkrip'),
            'nilai_lolos': wizard.get('nilai_lolos'),
            'current_pengguna': current_pengguna,
            'matkul_form': forms.get('matkul_form') or PublicPilihMatkulForm(),
            'transkrip_form': forms.get('transkrip_form') or PublicTranskripForm(),
            'berkas_form': forms.get('berkas_form') or PublicBerkasPendaftaranForm(current_pengguna=current_pengguna),
        }
        if step == 'transkrip' and not matkul:
            wizard['step'] = 'matkul'
            request.session.modified = True
            context['step'] = 'matkul'
        if step == 'berkas' and (not matkul or not wizard.get('nilai_lolos')):
            wizard['step'] = 'transkrip'
            request.session.modified = True
            context['step'] = 'transkrip'
        return render(request, self.template_name, context)

    def get_selected_matkul(self, wizard):
        matkul_id = wizard.get('matkul_id')
        if not matkul_id:
            return None
        return MataKuliahAsleb.objects.filter(pk=matkul_id, aktif=True).first()
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271


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
<<<<<<< HEAD
    messages.success(request, 'Pendaftaran asleb ditandai diterima.')
=======
    messages.success(request, 'Pendaftaran aslab ditandai diterima.')
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271
    return redirect('pendaftaran_asleb:pendaftaran_list')


@require_POST
def reject_pendaftaran(request, pk):
    pendaftaran = get_object_or_404(PendaftaranAsleb, pk=pk)
    pendaftaran.status = 'ditolak'
    pendaftaran.save(update_fields=['status', 'diperbarui_pada'])
<<<<<<< HEAD
    messages.warning(request, 'Pendaftaran asleb ditandai ditolak.')
=======
    messages.warning(request, 'Pendaftaran aslab ditandai ditolak.')
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271
    return redirect('pendaftaran_asleb:pendaftaran_list')


@require_POST
def generate_asleb(request, pk):
    pendaftaran = get_object_or_404(PendaftaranAsleb, pk=pk)

    if pendaftaran.status != 'diterima':
<<<<<<< HEAD
        messages.error(request, 'Hanya pendaftaran yang diterima yang bisa digenerate ke Data Asleb.')
=======
        messages.error(request, 'Hanya pendaftaran yang diterima yang bisa digenerate ke Data Aslab.')
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271
        return redirect('pendaftaran_asleb:pendaftaran_list')

    create_or_update_asleb_from_pendaftaran(pendaftaran)
    pendaftaran.status = 'digenerate'
    pendaftaran.save(update_fields=['status', 'diperbarui_pada'])
<<<<<<< HEAD
    messages.success(request, 'Pendaftaran berhasil digenerate ke Data Asleb.')
=======
    messages.success(request, 'Pendaftaran berhasil digenerate ke Data Aslab.')
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271
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
<<<<<<< HEAD
        messages.success(request, f'{generated_count} pendaftar diterima berhasil digenerate ke Data Asleb.')
=======
        messages.success(request, f'{generated_count} pendaftar diterima berhasil digenerate ke Data Aslab.')
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271
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
<<<<<<< HEAD
        messages.success(request, f'Pendaftaran asleb berhasil {status}. Notifikasi email dikirim ke {notified_count} akun.')
    else:
        messages.success(request, f'Pendaftaran asleb berhasil {status}.')
=======
        messages.success(request, f'Pendaftaran aslab berhasil {status}. Notifikasi email dikirim ke {notified_count} akun.')
    else:
        messages.success(request, f'Pendaftaran aslab berhasil {status}.')
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271
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
<<<<<<< HEAD
            subject='Pendaftaran Asleb Project Laboran Dibuka',
=======
            subject='Pendaftaran Aslab Project Laboran Dibuka',
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271
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
<<<<<<< HEAD
            'catatan': f'Digenerate dari pendaftaran asleb tanggal {pendaftaran.tanggal_daftar:%d-%m-%Y}.',
=======
            'catatan': f'Digenerate dari pendaftaran aslab tanggal {pendaftaran.tanggal_daftar:%d-%m-%Y}.',
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271
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
