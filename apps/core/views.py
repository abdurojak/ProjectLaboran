from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from apps.pengguna.forms import PenggunaAppearanceForm


class PostOnlyDeleteMixin:
    def get(self, request, *args, **kwargs):
        if getattr(self, 'success_url', None):
            return redirect(self.success_url)
        return redirect(self.get_success_url())


class SettingsView(TemplateView):
    template_name = 'core/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pengguna = getattr(self.request, 'current_pengguna', None)
        context['pengguna'] = pengguna
        context['settings_cards'] = self.get_settings_cards(pengguna)
        context['appearance_form'] = kwargs.get('appearance_form') or PenggunaAppearanceForm(instance=pengguna)
        return context

    def post(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna:
            return redirect('pengguna:login')

        form = PenggunaAppearanceForm(request.POST, request.FILES, instance=pengguna)
        if form.is_valid():
            form.save()
            request.current_pengguna = pengguna
            return redirect('core:settings')

        return self.render_to_response(self.get_context_data(appearance_form=form))

    def get_settings_cards(self, pengguna):
        if not pengguna:
            return []

        cards = [
            {
                'title': 'Profil Saya',
                'description': 'Lihat dan perbarui identitas akun yang sedang digunakan.',
                'url': 'pengguna:detail',
                'args': [pengguna.pk],
                'icon': 'user-round',
            },
            {
                'title': 'Ganti Password',
                'description': 'Ubah password akun agar akses tetap aman.',
                'url': 'pengguna:detail',
                'args': [pengguna.pk],
                'icon': 'key-round',
            },
        ]

        if pengguna.role == 'admin':
            cards.extend([
                {
                    'title': 'Master Akademik',
                    'description': 'Kelola fakultas dan prodi yang muncul pada registrasi.',
                    'url': 'pengguna:master_akademik',
                    'args': [],
                    'icon': 'graduation-cap',
                },
                {
                    'title': 'Pengguna',
                    'description': 'Kelola akun dan role pengguna sistem.',
                    'url': 'pengguna:list',
                    'args': [],
                    'icon': 'users',
                },
            ])

        if pengguna.role in {'admin', 'laboran'}:
            cards.append({
                'title': 'Pendaftaran Aslab',
                'description': 'Buka/tutup pendaftaran dan kelola data mata kuliah aslab.',
                'url': 'pendaftaran_asleb:pendaftaran_list',
                'args': [],
                'icon': 'user-round-plus',
            })

        for card in cards:
            card['href'] = reverse(card['url'], args=card.get('args', []))
        return cards
