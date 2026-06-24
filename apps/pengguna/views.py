import random
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView, View

from apps.core.views import PostOnlyDeleteMixin

from .forms import (
    ChangePasswordForm,
    ForgotPasswordRequestForm,
    LoginPenggunaForm,
    PenggunaForm,
    PenggunaProfileForm,
    RegisterPenggunaForm,
    ResetPasswordForm,
    VerificationCodeForm,
)
from .models import Pengguna


OTP_SESSION_KEY = 'pengguna_otp'
OTP_EXPIRE_MINUTES = 10


def generate_otp_code():
    return f'{random.randint(0, 999999):06d}'


def store_otp(request, purpose, pengguna, method):
    code = generate_otp_code()
    request.session[OTP_SESSION_KEY] = {
        'purpose': purpose,
        'pengguna_id': pengguna.pk,
        'method': method,
        'code': code,
        'expires_at': (timezone.now() + timedelta(minutes=OTP_EXPIRE_MINUTES)).isoformat(),
    }
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


def send_verification_code(request, pengguna, method, purpose):
    code = store_otp(request, purpose, pengguna, method)

    if method == 'email':
        send_mail(
            subject='Kode Verifikasi Project Laboran',
            message=f'Kode verifikasi Anda adalah {code}. Kode berlaku {OTP_EXPIRE_MINUTES} menit.',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@project-laboran.local'),
            recipient_list=[pengguna.email],
            fail_silently=True,
        )
        messages.info(request, f'Kode verifikasi dikirim ke email {pengguna.email}.')
    else:
        messages.info(
            request,
            f'Kode verifikasi No HP untuk simulasi lokal: {code}. Integrasi SMS/WhatsApp bisa ditambahkan nanti.',
        )


class PenggunaListView(ListView):
    model = Pengguna
    template_name = 'pengguna/list.html'
    context_object_name = 'pengguna_list'


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
        return context


class PenggunaCreateView(CreateView):
    model = Pengguna
    form_class = PenggunaForm
    template_name = 'pengguna/form.html'
    success_url = reverse_lazy('pengguna:list')


class PenggunaUpdateView(UpdateView):
    model = Pengguna
    form_class = PenggunaForm
    template_name = 'pengguna/form.html'
    context_object_name = 'pengguna'
    success_url = reverse_lazy('pengguna:list')


class PenggunaDeleteView(PostOnlyDeleteMixin, DeleteView):
    model = Pengguna
    template_name = 'pengguna/confirm_delete.html'
    context_object_name = 'pengguna'
    success_url = reverse_lazy('pengguna:list')


class PenggunaChangePasswordView(View):
    def post(self, request, pk, *args, **kwargs):
        pengguna = Pengguna.objects.get(pk=pk)
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
        pengguna = Pengguna.objects.get(pk=pk)
        form = PenggunaProfileForm(
            request.POST,
            request.FILES,
            instance=pengguna,
            current_pengguna=getattr(request, 'current_pengguna', None),
        )

        if form.is_valid():
            form.save()
            messages.success(request, 'Profil pengguna berhasil diperbarui.')
        else:
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)

        return redirect('pengguna:detail', pk=pk)


class PenggunaLoginView(FormView):
    template_name = 'pengguna/login.html'
    form_class = LoginPenggunaForm
    success_url = reverse_lazy('dashboard:home')

    def form_valid(self, form):
        pengguna = form.cleaned_data['pengguna']
        self.request.session['pengguna_id'] = pengguna.pk
        messages.success(self.request, f'Selamat datang, {pengguna.nama_pengguna}.')
        return redirect(self.request.GET.get('next') or self.success_url)


class PenggunaRegisterView(CreateView):
    model = Pengguna
    form_class = RegisterPenggunaForm
    template_name = 'pengguna/register.html'
    success_url = reverse_lazy('pengguna:verify_register')

    def form_valid(self, form):
        response = super().form_valid(form)
        send_verification_code(
            self.request,
            self.object,
            form.cleaned_data['verification_method'],
            'register',
        )
        messages.success(self.request, 'Registrasi berhasil. Masukkan kode verifikasi untuk mengaktifkan akun.')
        return response


class PenggunaVerifyRegisterView(FormView):
    template_name = 'pengguna/verify_register.html'
    form_class = VerificationCodeForm
    success_url = reverse_lazy('dashboard:home')

    def dispatch(self, request, *args, **kwargs):
        if not get_pending_otp(request, 'register'):
            messages.warning(request, 'Tidak ada proses verifikasi aktif. Silakan registrasi ulang.')
            return redirect('pengguna:register')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        otp = get_pending_otp(self.request, 'register')
        if form.cleaned_data['kode'] != otp['code']:
            form.add_error('kode', 'Kode verifikasi tidak sesuai.')
            return self.form_invalid(form)

        pengguna = Pengguna.objects.get(pk=otp['pengguna_id'])
        pengguna.is_verified = True
        pengguna.save(update_fields=['is_verified', 'diperbarui_pada'])
        self.request.session.pop(OTP_SESSION_KEY, None)
        self.request.session['pengguna_id'] = pengguna.pk
        messages.success(self.request, 'Akun berhasil diverifikasi. Anda sudah masuk ke LabHub.')
        return redirect(self.success_url)


class ForgotPasswordRequestView(FormView):
    template_name = 'pengguna/forgot_password.html'
    form_class = ForgotPasswordRequestForm
    success_url = reverse_lazy('pengguna:reset_password')

    def form_valid(self, form):
        try:
            pengguna = Pengguna.objects.get(nim_nik=form.cleaned_data['nim_nik'])
        except Pengguna.DoesNotExist:
            form.add_error('nim_nik', 'Pengguna dengan NIM/NIK ini tidak ditemukan.')
            return self.form_invalid(form)

        send_verification_code(
            self.request,
            pengguna,
            form.cleaned_data['verification_method'],
            'reset_password',
        )
        messages.success(self.request, 'Kode reset password berhasil dibuat.')
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
        if form.cleaned_data['kode'] != otp['code']:
            form.add_error('kode', 'Kode verifikasi tidak sesuai.')
            return self.form_invalid(form)

        pengguna = Pengguna.objects.get(pk=otp['pengguna_id'])
        pengguna.password = make_password(form.cleaned_data['password'])
        pengguna.is_verified = True
        pengguna.save(update_fields=['password', 'is_verified', 'diperbarui_pada'])
        self.request.session.pop(OTP_SESSION_KEY, None)
        messages.success(self.request, 'Password berhasil diganti. Silakan login dengan password baru.')
        return redirect(self.success_url)


class PenggunaLogoutView(View):
    def post(self, request, *args, **kwargs):
        request.session.pop('pengguna_id', None)
        messages.success(request, 'Anda sudah keluar.')
        return redirect('pengguna:login')
