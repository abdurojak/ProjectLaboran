from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView, View

from .forms import LoginPenggunaForm, PenggunaForm, RegisterPenggunaForm
from .models import Pengguna


class PenggunaListView(ListView):
    model = Pengguna
    template_name = 'pengguna/list.html'
    context_object_name = 'pengguna_list'


class PenggunaDetailView(DetailView):
    model = Pengguna
    template_name = 'pengguna/detail.html'
    context_object_name = 'pengguna'


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


class PenggunaDeleteView(DeleteView):
    model = Pengguna
    template_name = 'pengguna/confirm_delete.html'
    context_object_name = 'pengguna'
    success_url = reverse_lazy('pengguna:list')


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
    success_url = reverse_lazy('dashboard:home')

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session['pengguna_id'] = self.object.pk
        messages.success(self.request, 'Registrasi berhasil. Anda sudah masuk ke LabHub.')
        return response


class PenggunaLogoutView(View):
    def post(self, request, *args, **kwargs):
        request.session.pop('pengguna_id', None)
        messages.success(request, 'Anda sudah keluar.')
        return redirect('pengguna:login')
