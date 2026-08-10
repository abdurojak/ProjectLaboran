import hashlib
import secrets
from smtplib import SMTPException
from datetime import timedelta
from urllib.parse import urlencode, urljoin

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView, View
from django.views.decorators.http import require_POST

from apps.asleb.models import Asleb
from apps.core.views import PostOnlyDeleteMixin
from apps.asleb.services import link_peserta_praktikum_to_pengguna
from apps.core.emails import send_branded_email
from apps.pendaftaran_asleb.models import PendaftaranAsleb

from .forms import (
    ChangePasswordForm,
    FakultasForm,
    ForgotPasswordRequestForm,
    LoginPenggunaForm,
    PenggunaForm,
    PenggunaProfileForm,
    PengalamanPenggunaForm,
    PendidikanPenggunaForm,
    OrganisasiPenggunaForm,
    ProyekPenggunaForm,
    SertifikasiPenggunaForm,
    ProdiForm,
    RegisterPenggunaForm,
    ResetPasswordForm,
    VerificationCodeForm,
)
from .cv import build_cv_pdf
from .models import Fakultas, PengalamanPengguna, Pengguna, Prodi, School


OTP_SESSION_KEY = 'pengguna_otp'
PENDING_REGISTER_USER_KEY = 'pengguna_pending_register_id'
OTP_EXPIRE_MINUTES = 10
OTP_MAX_ATTEMPTS = 5

RIWAYAT_FORM_CLASSES = {
    'pengalaman': PengalamanPenggunaForm,
    'pendidikan': PendidikanPenggunaForm,
    'organisasi': OrganisasiPenggunaForm,
    'proyek': ProyekPenggunaForm,
    'sertifikasi': SertifikasiPenggunaForm,
}
RIWAYAT_CATEGORY_META = {
    'pengalaman': {'label': 'Pengalaman', 'icon': 'briefcase-business', 'description': 'Posisi kerja, magang, atau pengalaman profesional.'},
    'pendidikan': {'label': 'Pendidikan', 'icon': 'graduation-cap', 'description': 'Sekolah, kampus, jenjang, dan program studi.'},
    'organisasi': {'label': 'Organisasi', 'icon': 'users-round', 'description': 'Kepengurusan dan kegiatan organisasi.'},
    'proyek': {'label': 'Proyek', 'icon': 'folder-kanban', 'description': 'Proyek, peran, teknologi, dan tautan hasil kerja.'},
    'sertifikasi': {'label': 'Lisensi & Sertifikat', 'icon': 'badge-check', 'description': 'Sertifikat, penerbit, kredensial, dan dokumen pendukung.'},
}


class AdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role != 'admin':
            messages.error(request, 'Hanya admin yang bisa mengelola data ini.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)


class AdminPenggunaRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role != 'admin':
            messages.error(request, 'Hanya admin yang bisa menambah, mengubah, atau menghapus pengguna.')
            return redirect('pengguna:list')
        return super().dispatch(request, *args, **kwargs)


def generate_otp_code():
    return f'{secrets.randbelow(1_000_000):06d}'


def login_attempt_cache_key(request):
    identifier = request.POST.get('nim_nik', '').strip().lower()
    address = request.META.get('REMOTE_ADDR', '')
    digest = hashlib.sha256(f'{address}:{identifier}'.encode()).hexdigest()
    return f'pengguna-login-attempt:{digest}'


def password_reset_request_cache_key(request, identifier):
    address = request.META.get('REMOTE_ADDR', '')
    digest = hashlib.sha256(f'{address}:{identifier.strip().lower()}'.encode()).hexdigest()
    return f'pengguna-password-reset:{digest}'


def otp_resend_cache_key(request, pengguna):
    address = request.META.get('REMOTE_ADDR', '')
    digest = hashlib.sha256(f'{address}:{pengguna.pk}:register'.encode()).hexdigest()
    return f'pengguna-otp-resend:{digest}'


def build_public_url(route_name, *args):
    base_url = settings.PUBLIC_ACCESS_BASE_URL.rstrip('/') + '/'
    return urljoin(base_url, reverse(route_name, args=args).lstrip('/'))


def build_public_url_with_query(route_name, query, *args):
    return f'{build_public_url(route_name, *args)}?{urlencode(query)}'


def store_otp(request, purpose, pengguna, method, extra=None):
    code = generate_otp_code()
    otp_data = {
        'purpose': purpose,
        'pengguna_id': pengguna.pk if pengguna else None,
        'method': method,
        'code': code,
        'attempts': 0,
        'expires_at': (timezone.now() + timedelta(minutes=OTP_EXPIRE_MINUTES)).isoformat(),
    }
    if extra:
        otp_data.update(extra)

    request.session[OTP_SESSION_KEY] = otp_data
    request.session.modified = True
    return code


def get_pending_otp(request, purpose):
    otp = request.session.get(OTP_SESSION_KEY)
    if not otp or otp.get('purpose') != purpose:
        return None

    expires_at = timezone.datetime.fromisoformat(otp['expires_at'])
    if timezone.is_naive(expires_at):
        expires_at = timezone.make_aware(expires_at)

    if timezone.now() > expires_at:
        request.session.pop(OTP_SESSION_KEY, None)
        return None

    return otp


def get_pending_registration_user(request):
    pengguna_id = request.session.get(PENDING_REGISTER_USER_KEY)
    if not pengguna_id:
        return None
    pengguna = Pengguna.objects.filter(pk=pengguna_id, is_verified=False).first()
    if not pengguna:
        request.session.pop(PENDING_REGISTER_USER_KEY, None)
    return pengguna


def otp_code_matches(request, otp, submitted_code):
    if secrets.compare_digest(str(submitted_code), str(otp['code'])):
        return True

    otp['attempts'] = int(otp.get('attempts', 0)) + 1
    if otp['attempts'] >= OTP_MAX_ATTEMPTS:
        request.session.pop(OTP_SESSION_KEY, None)
        return False

    request.session[OTP_SESSION_KEY] = otp
    request.session.modified = True
    return False


def send_verification_code(
    request,
    pengguna,
    method,
    purpose,
    extra=None,
    show_delivery_message=True,
):
    code = store_otp(request, purpose, pengguna, method, extra=extra)
    if purpose == 'register':
        verification_url = build_public_url_with_query('pengguna:verify_register', {'kode': code})
    elif purpose == 'profile_phone':
        verification_url = build_public_url('pengguna:verify_profile_phone', pengguna.pk)
    else:
        verification_url = build_public_url('pengguna:reset_password')

    if method == 'email':
        is_simulated_email = (
            settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend'
            or not settings.EMAIL_HOST_PASSWORD
            or settings.EMAIL_HOST_PASSWORD == 'change-me'
        )
        if is_simulated_email:
            if show_delivery_message:
                messages.info(
                    request,
                    f'Kode verifikasi email untuk simulasi lokal: {code}. Link verifikasi: {verification_url}. SMTP belum aktif sampai EMAIL_HOST_PASSWORD diganti dari change-me.',
                )
            return True
        else:
            try:
                text_body = (
                    f'Kode verifikasi Anda adalah {code}.\n'
                    f'Kode berlaku {OTP_EXPIRE_MINUTES} menit.\n\n'
                    f'Buka halaman verifikasi: {verification_url}'
                )
                send_branded_email(
                    subject='Kode Verifikasi Project Laboran',
                    recipients=[pengguna.email],
                    text_body=text_body,
                    title='Verifikasi akun Anda',
                    greeting=f'Halo {pengguna.nama_pengguna},',
                    intro='Gunakan kode berikut untuk melanjutkan proses verifikasi akun LabHub.',
                    highlight=code,
                    action_url=verification_url,
                    action_label='Buka Halaman Verifikasi',
                    note=f'Kode hanya berlaku selama {OTP_EXPIRE_MINUTES} menit. Jangan berikan kode ini kepada siapa pun.',
                    fail_silently=False,
                )
                if show_delivery_message:
                    messages.info(request, f'Kode verifikasi dikirim ke email {pengguna.email}. Link verifikasi memakai {verification_url}.')
                return True
            except (OSError, SMTPException):
                if show_delivery_message:
                    messages.error(
                        request,
                        'Email verifikasi belum dapat dikirim. Silakan coba lagi atau hubungi pengelola LabHub.',
                    )
                return False
    else:
        messages.info(
            request,
            f'Kode verifikasi No HP untuk simulasi lokal: {code}. Link verifikasi: {verification_url}. Integrasi SMS/WhatsApp bisa ditambahkan nanti.',
        )
        return True


class PenggunaListView(ListView):
    model = Pengguna
    template_name = 'pengguna/list.html'
    context_object_name = 'pengguna_list'

    ROLE_GROUPS = [
        ('Mahasiswa', 'mahasiswa'),
        ('Laboran', 'laboran'),
        ('Asisten Lab', 'asisten_lab'),
    ]

    def get_queryset(self):
        queryset = Pengguna.objects.exclude(role='admin').order_by('role', 'nama_pengguna')
        pengguna = getattr(self.request, 'current_pengguna', None)

        if pengguna and pengguna.role == 'laboran':
            return queryset.filter(role__in=['mahasiswa', 'asisten_lab'])

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pengguna = getattr(self.request, 'current_pengguna', None)
        visible_roles = ['mahasiswa', 'laboran', 'asisten_lab']
        if pengguna and pengguna.role == 'laboran':
            visible_roles = ['mahasiswa', 'asisten_lab']

        grouped_users = []
        for title, role in self.ROLE_GROUPS:
            if role not in visible_roles:
                continue
            users = [item for item in context['pengguna_list'] if item.role == role]
            grouped_users.append({
                'title': title,
                'role': role,
                'users': users,
                'count': len(users),
            })

        context['grouped_users'] = grouped_users
        context['can_manage_users'] = bool(pengguna and pengguna.role == 'admin')
        return context


class PenggunaDetailView(DetailView):
    model = Pengguna
    template_name = 'pengguna/detail.html'
    context_object_name = 'pengguna'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile_form'] = PenggunaProfileForm(
            instance=self.object,
            current_pengguna=getattr(self.request, 'current_pengguna', None),
        )
        context['asleb_profile'] = None
        context['asleb_profile'] = Asleb.objects.filter(nim=self.object.nim_nik).first()
        context['asleb_history'] = PendaftaranAsleb.objects.filter(
            nim=self.object.nim_nik,
        ).select_related('periode', 'matkul').order_by('-periode__tahun', '-periode__semester', 'matkul__nama')
        riwayat = self.object.pengalaman.all()
        context['riwayat_sections'] = [
            (key, label, riwayat.filter(kategori=key))
            for key, label in PengalamanPengguna.KATEGORI_CHOICES
        ]
        context['riwayat_category_forms'] = [
            {
                'key': key,
                **RIWAYAT_CATEGORY_META[key],
                'form': form_class(),
            }
            for key, form_class in RIWAYAT_FORM_CLASSES.items()
        ]
        context['riwayat_edit_forms'] = [
            {
                'item': item,
                'category_meta': RIWAYAT_CATEGORY_META[item.kategori],
                'form': RIWAYAT_FORM_CLASSES[item.kategori](instance=item),
            }
            for item in riwayat.filter(otomatis=False)
        ]
        return context


class PenggunaCreateView(AdminPenggunaRequiredMixin, CreateView):
    model = Pengguna
    form_class = PenggunaForm
    template_name = 'pengguna/form.html'
    success_url = reverse_lazy('pengguna:list')


class PenggunaUpdateView(AdminPenggunaRequiredMixin, UpdateView):
    model = Pengguna
    form_class = PenggunaForm
    template_name = 'pengguna/form.html'
    context_object_name = 'pengguna'
    success_url = reverse_lazy('pengguna:list')


class PenggunaDeleteView(AdminPenggunaRequiredMixin, PostOnlyDeleteMixin, DeleteView):
    model = Pengguna
    template_name = 'pengguna/confirm_delete.html'
    context_object_name = 'pengguna'
    success_url = reverse_lazy('pengguna:list')


class MasterAkademikView(AdminRequiredMixin, ListView):
    model = Fakultas
    template_name = 'pengguna/master_akademik.html'
    context_object_name = 'fakultas_list'

    def get_queryset(self):
        return Fakultas.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['prodi_list'] = Prodi.objects.all()
        return context


class FakultasCreateView(AdminRequiredMixin, CreateView):
    model = Fakultas
    form_class = FakultasForm
    template_name = 'pengguna/master_form.html'
    success_url = reverse_lazy('pengguna:master_akademik')
    extra_context = {
        'title': 'Tambah Fakultas',
        'eyebrow': 'Master Akademik',
        'description': 'Tambahkan pilihan fakultas yang bisa dipilih saat registrasi.',
    }


class FakultasUpdateView(AdminRequiredMixin, UpdateView):
    model = Fakultas
    form_class = FakultasForm
    template_name = 'pengguna/master_form.html'
    success_url = reverse_lazy('pengguna:master_akademik')
    extra_context = {
        'title': 'Edit Fakultas',
        'eyebrow': 'Master Akademik',
        'description': 'Ubah nama atau status aktif fakultas.',
    }


class ProdiCreateView(AdminRequiredMixin, CreateView):
    model = Prodi
    form_class = ProdiForm
    template_name = 'pengguna/master_form.html'
    success_url = reverse_lazy('pengguna:master_akademik')
    extra_context = {
        'title': 'Tambah Prodi',
        'eyebrow': 'Master Akademik',
        'description': 'Tambahkan pilihan prodi yang bisa dipilih saat registrasi.',
    }


class ProdiUpdateView(AdminRequiredMixin, UpdateView):
    model = Prodi
    form_class = ProdiForm
    template_name = 'pengguna/master_form.html'
    success_url = reverse_lazy('pengguna:master_akademik')
    extra_context = {
        'title': 'Edit Prodi',
        'eyebrow': 'Master Akademik',
        'description': 'Ubah nama atau status aktif prodi.',
    }


class PenggunaChangePasswordView(View):
    def post(self, request, pk, *args, **kwargs):
        pengguna = get_object_or_404(Pengguna, pk=pk)
        current = getattr(request, 'current_pengguna', None)
        if not current or (current.role != 'admin' and current.pk != pengguna.pk):
            messages.error(request, 'Anda tidak memiliki akses untuk mengganti password akun ini.')
            return redirect('dashboard:home')
        form = ChangePasswordForm(request.POST)

        if form.is_valid():
            pengguna.password = make_password(form.cleaned_data['password'])
            pengguna.save(update_fields=['password', 'diperbarui_pada'])
            messages.success(request, 'Password pengguna berhasil diganti.')
        else:
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)

        return redirect('pengguna:detail', pk=pk)


class PenggunaUpdateProfileView(View):
    def post(self, request, pk, *args, **kwargs):
        pengguna = get_object_or_404(Pengguna, pk=pk)
        current = getattr(request, 'current_pengguna', None)
        if not current or (current.role != 'admin' and current.pk != pengguna.pk):
            messages.error(request, 'Anda tidak memiliki akses untuk mengubah profil akun ini.')
            return redirect('dashboard:home')
        form = PenggunaProfileForm(
            request.POST,
            request.FILES,
            instance=pengguna,
            current_pengguna=current,
        )

        if form.is_valid():
            form.save()
            messages.success(request, 'Profil pengguna berhasil diperbarui.')
        else:
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)

        return redirect('pengguna:detail', pk=pk)


class PengalamanOwnerMixin:
    def dispatch(self, request, *args, **kwargs):
        self.profile_user = get_object_or_404(Pengguna, pk=kwargs['user_pk'])
        current = getattr(request, 'current_pengguna', None)
        if not current or (current.role != 'admin' and current.pk != self.profile_user.pk):
            messages.error(request, 'Anda tidak memiliki akses untuk mengubah pengalaman ini.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)


class PengalamanCreateView(PengalamanOwnerMixin, CreateView):
    model = PengalamanPengguna
    template_name = 'pengguna/pengalaman_form.html'

    def get_category(self):
        return self.request.GET.get('kategori', '').strip()

    def get(self, request, *args, **kwargs):
        category = self.get_category()
        if not category:
            return render(request, self.template_name, self.get_category_context())
        if category not in RIWAYAT_FORM_CLASSES:
            messages.error(request, 'Kategori profil yang dipilih tidak valid.')
            return redirect('pengguna:experience_create', user_pk=self.profile_user.pk)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.get_category() not in RIWAYAT_FORM_CLASSES:
            messages.error(request, 'Pilih kategori profil sebelum mengisi data.')
            return redirect('pengguna:experience_create', user_pk=self.profile_user.pk)
        return super().post(request, *args, **kwargs)

    def get_form_class(self):
        return RIWAYAT_FORM_CLASSES[self.get_category()]

    def get_category_context(self):
        return {
            'view': self,
            'profile_user': self.profile_user,
            'category_choices': [
                {'key': key, **meta}
                for key, meta in RIWAYAT_CATEGORY_META.items()
            ],
            'selecting_category': True,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.get_category()
        context.update({
            'profile_user': self.profile_user,
            'selected_category': category,
            'category_meta': RIWAYAT_CATEGORY_META[category],
        })
        return context

    def form_valid(self, form):
        form.instance.pengguna = self.profile_user
        label = RIWAYAT_CATEGORY_META[self.get_category()]['label']
        messages.success(self.request, f'Data {label.lower()} berhasil ditambahkan.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('pengguna:detail', args=[self.profile_user.pk])


class PengalamanUpdateView(PengalamanOwnerMixin, UpdateView):
    model = PengalamanPengguna
    template_name = 'pengguna/pengalaman_form.html'
    pk_url_kwarg = 'experience_pk'

    def get_queryset(self):
        return super().get_queryset().filter(pengguna=self.profile_user, otomatis=False)

    def get_form_class(self):
        return RIWAYAT_FORM_CLASSES[self.object.kategori]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'profile_user': self.profile_user,
            'selected_category': self.object.kategori,
            'category_meta': RIWAYAT_CATEGORY_META[self.object.kategori],
        })
        return context

    def get_success_url(self):
        label = RIWAYAT_CATEGORY_META[self.object.kategori]['label']
        messages.success(self.request, f'Data {label.lower()} berhasil diperbarui.')
        return reverse('pengguna:detail', args=[self.profile_user.pk])


@require_POST
def delete_pengalaman(request, user_pk, experience_pk):
    profile_user = get_object_or_404(Pengguna, pk=user_pk)
    current = getattr(request, 'current_pengguna', None)
    if not current or (current.role != 'admin' and current.pk != profile_user.pk):
        messages.error(request, 'Anda tidak memiliki akses untuk menghapus pengalaman ini.')
        return redirect('dashboard:home')
    pengalaman = get_object_or_404(PengalamanPengguna, pk=experience_pk, pengguna=profile_user, otomatis=False)
    pengalaman.delete()
    messages.success(request, 'Pengalaman berhasil dihapus.')
    return redirect('pengguna:detail', pk=profile_user.pk)


class SchoolSearchView(View):
    def get(self, request, *args, **kwargs):
        if not getattr(request, 'current_pengguna', None):
            return JsonResponse({'results': [], 'error': 'Silakan login terlebih dahulu.'}, status=401)

        keyword = request.GET.get('q', '').strip()
        level = request.GET.get('level', '').strip().upper()
        province = request.GET.get('province', '').strip()
        city = request.GET.get('city', '').strip()

        if len(keyword) < 2:
            return JsonResponse({'results': []})

        queryset = School.objects.filter(aktif=True).filter(
            Q(nama__icontains=keyword) | Q(npsn__icontains=keyword)
        )
        if level in {'SD', 'SMP', 'SMA', 'SMK'}:
            queryset = queryset.filter(jenjang=level)
        if province:
            queryset = queryset.filter(provinsi__icontains=province)
        if city:
            queryset = queryset.filter(kabupaten_kota__icontains=city)

        results = []
        for school in queryset.order_by('nama')[:20]:
            location = ', '.join(part for part in [school.kabupaten_kota, school.provinsi] if part)
            results.append({
                'id': school.pk,
                'npsn': school.npsn,
                'nama': school.nama,
                'jenjang': school.jenjang,
                'status': school.get_status_display(),
                'location': location,
                'label': school.nama,
                'description': f'NPSN: {school.npsn} - {location or "Lokasi belum tersedia"}',
            })
        return JsonResponse({'results': results})


def download_cv(request, user_pk):
    profile_user = get_object_or_404(Pengguna, pk=user_pk)
    current = getattr(request, 'current_pengguna', None)
    if not current or (current.role not in {'admin', 'laboran'} and current.pk != profile_user.pk):
        messages.error(request, 'Anda tidak memiliki akses untuk mengunduh CV ini.')
        return redirect('dashboard:home')
    response = HttpResponse(build_cv_pdf(profile_user), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="cv-{profile_user.nim_nik}.pdf"'
    return response


class PenggunaVerifyProfilePhoneView(FormView):
    template_name = 'pengguna/verify_profile_phone.html'
    form_class = VerificationCodeForm

    def dispatch(self, request, *args, **kwargs):
        otp = get_pending_otp(request, 'profile_phone')
        if not otp or otp.get('pengguna_id') != self.kwargs['pk']:
            messages.warning(request, 'Tidak ada proses verifikasi No HP aktif.')
            return redirect('pengguna:detail', pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        otp = get_pending_otp(self.request, 'profile_phone')
        if not otp_code_matches(self.request, otp, form.cleaned_data['kode']):
            if not get_pending_otp(self.request, 'profile_phone'):
                messages.error(self.request, 'Batas percobaan kode tercapai. Silakan ubah nomor HP kembali.')
                return redirect('pengguna:detail', pk=self.kwargs['pk'])
            form.add_error('kode', 'Kode verifikasi tidak sesuai.')
            return self.form_invalid(form)

        pengguna = Pengguna.objects.get(pk=otp['pengguna_id'])
        pengguna.no_hp = otp.get('new_no_hp', pengguna.no_hp)
        pengguna.save(update_fields=['no_hp', 'diperbarui_pada'])
        self.request.session.pop(OTP_SESSION_KEY, None)
        messages.success(self.request, 'No HP baru berhasil diverifikasi dan disimpan.')
        return redirect('pengguna:detail', pk=pengguna.pk)


class PenggunaLoginView(FormView):
    template_name = 'pengguna/login.html'
    form_class = LoginPenggunaForm
    success_url = reverse_lazy('dashboard:home')

    def post(self, request, *args, **kwargs):
        cache_key = login_attempt_cache_key(request)
        attempts = int(cache.get(cache_key, 0))
        if attempts >= settings.LOGIN_MAX_ATTEMPTS:
            form = self.get_form()
            form.add_error(None, 'Terlalu banyak percobaan login. Silakan coba kembali beberapa saat lagi.')
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        if self.request.method == 'POST' and self.request.POST.get('nim_nik'):
            cache_key = login_attempt_cache_key(self.request)
            attempts = int(cache.get(cache_key, 0)) + 1
            cache.set(cache_key, attempts, settings.LOGIN_LOCKOUT_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        pengguna = form.cleaned_data['pengguna']
        cache.delete(login_attempt_cache_key(self.request))
        self.request.session.cycle_key()
        self.request.session['pengguna_id'] = pengguna.pk
        messages.success(self.request, f'Selamat datang, {pengguna.nama_pengguna}.')
        next_url = self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return redirect(next_url)
        return redirect(self.success_url)


class PenggunaRegisterView(CreateView):
    model = Pengguna
    form_class = RegisterPenggunaForm
    template_name = 'pengguna/register.html'
    success_url = reverse_lazy('pengguna:verify_register')

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session[PENDING_REGISTER_USER_KEY] = self.object.pk
        self.request.session.modified = True
        send_verification_code(
            self.request,
            self.object,
            'email',
            'register',
        )
        messages.success(self.request, 'Registrasi berhasil. Masukkan kode verifikasi untuk mengaktifkan akun.')
        return response

    def form_invalid(self, form):
        messages.error(
            self.request,
            'Registrasi gagal. Periksa kembali data yang ditandai pada formulir.',
        )
        return super().form_invalid(form)


class PenggunaVerifyRegisterView(FormView):
    template_name = 'pengguna/verify_register.html'
    form_class = VerificationCodeForm
    success_url = reverse_lazy('dashboard:home')

    def dispatch(self, request, *args, **kwargs):
        if not get_pending_otp(request, 'register') and not get_pending_registration_user(request):
            messages.warning(request, 'Tidak ada proses verifikasi aktif. Silakan registrasi ulang.')
            return redirect('pengguna:register')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['has_active_otp'] = bool(get_pending_otp(self.request, 'register'))
        context['pending_user'] = get_pending_registration_user(self.request)
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'resend':
            return self.resend_code()
        return super().post(request, *args, **kwargs)

    def resend_code(self):
        pengguna = get_pending_registration_user(self.request)
        if not pengguna:
            messages.warning(self.request, 'Akun pending tidak ditemukan. Silakan registrasi kembali.')
            return redirect('pengguna:register')

        cache_key = otp_resend_cache_key(self.request, pengguna)
        request_count = int(cache.get(cache_key, 0))
        if request_count >= settings.OTP_RESEND_MAX_REQUESTS:
            messages.error(
                self.request,
                'Batas kirim ulang kode tercapai. Silakan tunggu beberapa saat sebelum mencoba kembali.',
            )
            return redirect('pengguna:verify_register')

        cache.set(
            cache_key,
            request_count + 1,
            settings.OTP_RESEND_WINDOW_SECONDS,
        )
        delivered = send_verification_code(
            self.request,
            pengguna,
            'email',
            'register',
        )
        if delivered:
            messages.success(self.request, 'Kode verifikasi baru berhasil dikirim.')
        return redirect('pengguna:verify_register')

    def get(self, request, *args, **kwargs):
        kode = request.GET.get('kode', '').strip()
        if kode:
            form = self.form_class(data={'kode': kode})
            if form.is_valid():
                return self.form_valid(form)
            return self.form_invalid(form)

        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        otp = get_pending_otp(self.request, 'register')
        if not otp:
            form.add_error('kode', 'Kode sudah kedaluwarsa. Kirim ulang kode untuk melanjutkan.')
            return self.form_invalid(form)
        if not otp_code_matches(self.request, otp, form.cleaned_data['kode']):
            if not get_pending_otp(self.request, 'register'):
                messages.error(self.request, 'Batas percobaan kode tercapai. Kirim ulang kode untuk melanjutkan.')
                return redirect('pengguna:verify_register')
            form.add_error('kode', 'Kode verifikasi tidak sesuai.')
            return self.form_invalid(form)

        pengguna = Pengguna.objects.get(pk=otp['pengguna_id'])
        pengguna.is_verified = True
        pengguna.save(update_fields=['is_verified', 'diperbarui_pada'])
        linked_count = link_peserta_praktikum_to_pengguna(pengguna)
        self.request.session.pop(OTP_SESSION_KEY, None)
        self.request.session.pop(PENDING_REGISTER_USER_KEY, None)
        cache.delete(otp_resend_cache_key(self.request, pengguna))
        self.request.session.cycle_key()
        self.request.session['pengguna_id'] = pengguna.pk
        if linked_count:
            messages.success(
                self.request,
                f'Akun berhasil diverifikasi dan terhubung ke {linked_count} data peserta praktikum. Anda sudah masuk ke LabHub.',
            )
        else:
            messages.success(self.request, 'Akun berhasil diverifikasi. Anda sudah masuk ke LabHub.')
        return redirect(self.success_url)


class ForgotPasswordRequestView(FormView):
    template_name = 'pengguna/forgot_password.html'
    form_class = ForgotPasswordRequestForm
    success_url = reverse_lazy('pengguna:reset_password')

    def form_valid(self, form):
        identifier = form.cleaned_data['nim_nik'].strip()
        cache_key = password_reset_request_cache_key(self.request, identifier)
        request_count = int(cache.get(cache_key, 0))
        pengguna = Pengguna.objects.filter(nim_nik=identifier).first()

        if request_count < settings.PASSWORD_RESET_MAX_REQUESTS:
            cache.set(
                cache_key,
                request_count + 1,
                settings.PASSWORD_RESET_WINDOW_SECONDS,
            )
            if pengguna:
                send_verification_code(
                    self.request,
                    pengguna,
                    'email',
                    'reset_password',
                    show_delivery_message=False,
                )
            else:
                store_otp(self.request, 'reset_password', None, 'email')
        else:
            # A decoy flow keeps the response indistinguishable while avoiding
            # repeated email delivery to a known account.
            store_otp(self.request, 'reset_password', None, 'email')

        messages.success(
            self.request,
            'Jika NIM/NIK terdaftar, kode reset password telah dikirim ke email akun.',
        )
        if settings.DEBUG and (
            settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend'
            or not settings.EMAIL_HOST_PASSWORD
            or settings.EMAIL_HOST_PASSWORD == 'change-me'
        ):
            messages.info(
                self.request,
                f"Kode simulasi lokal: {self.request.session[OTP_SESSION_KEY]['code']}.",
            )
        return redirect(self.success_url)


class ResetPasswordView(FormView):
    template_name = 'pengguna/reset_password.html'
    form_class = ResetPasswordForm
    success_url = reverse_lazy('pengguna:login')

    def dispatch(self, request, *args, **kwargs):
        if not get_pending_otp(request, 'reset_password'):
            messages.warning(request, 'Tidak ada proses reset password aktif. Silakan minta kode ulang.')
            return redirect('pengguna:forgot_password')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        otp = get_pending_otp(self.request, 'reset_password')
        if not otp_code_matches(self.request, otp, form.cleaned_data['kode']):
            if not get_pending_otp(self.request, 'reset_password'):
                messages.error(self.request, 'Batas percobaan kode tercapai. Silakan minta kode baru.')
                return redirect('pengguna:forgot_password')
            form.add_error('kode', 'Kode verifikasi tidak sesuai.')
            return self.form_invalid(form)

        pengguna_id = otp.get('pengguna_id')
        pengguna = Pengguna.objects.filter(pk=pengguna_id).first() if pengguna_id else None
        if not pengguna:
            self.request.session.pop(OTP_SESSION_KEY, None)
            messages.info(
                self.request,
                'Jika data akun valid, silakan gunakan kode terbaru yang dikirim ke email.',
            )
            return redirect('pengguna:forgot_password')
        if check_password(form.cleaned_data['password'], pengguna.password):
            form.add_error('password', 'Password baru tidak boleh sama dengan password yang sedang digunakan.')
            return self.form_invalid(form)

        pengguna.password = make_password(form.cleaned_data['password'])
        pengguna.is_verified = True
        pengguna.save(update_fields=['password', 'is_verified', 'diperbarui_pada'])
        self.request.session.pop(OTP_SESSION_KEY, None)
        messages.success(self.request, 'Password berhasil diganti. Silakan login dengan password baru.')
        return redirect(self.success_url)


class PenggunaLogoutView(View):
    def post(self, request, *args, **kwargs):
        request.session.flush()
        messages.success(request, 'Anda sudah keluar.')
        return redirect('pengguna:login')
