from django.core import mail
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.test import TestCase, TransactionTestCase
from django.urls import reverse


class GlobalBackgroundTests(TestCase):
    def test_base_background_tetap_saat_halaman_discroll(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, 'class="app-page-background"', html=False)
        self.assertContains(response, 'position: fixed;')
        self.assertContains(response, 'background: transparent !important;')

    def test_sidebar_touch_state_memakai_warna_tema(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, '-webkit-tap-highlight-color: transparent;')
        self.assertContains(response, '#dashboard-sidebar a:active')
        self.assertContains(response, 'tbody tr:active')
        self.assertContains(response, 'tbody tr:active td')
        self.assertContains(response, 'background-color: var(--sidebar-hover-bg) !important;')
        self.assertContains(response, 'background-color: var(--hover-bg) !important;')

    def test_badge_dark_mode_memakai_warna_kontras(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, 'html[data-theme="dark"] [class~="bg-brand-50"][class*="text-brand-"]')
        self.assertContains(response, 'html[data-theme="dark"] [class~="bg-amber-50"][class*="text-amber-"]')
        self.assertNotContains(response, 'html[data-theme="dark"] [class*="bg-slate-50"][class*="text-slate-"]')
        self.assertContains(response, 'color: #ccfbf1 !important;')
        self.assertContains(response, 'color: #fde68a !important;')

    def test_teal_brand_text_dark_mode_lebih_terang(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, 'html[data-theme="dark"] .text-brand-700')
        self.assertContains(response, 'html[data-theme="dark"] .text-teal-700')
        self.assertContains(response, 'html[data-theme="dark"] .text-cyan-700')
        self.assertContains(response, 'color: #5eead4 !important;')
        self.assertContains(response, 'color: #67e8f9 !important;')

    def test_surface_card_global_memakai_glass_card(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, '.surface-card,')
        self.assertContains(response, '.glass-card')
        self.assertContains(response, 'background: rgba(255, 255, 255, 0.50) !important;')
        self.assertContains(response, 'html[data-theme="dark"] .surface-card')
        self.assertContains(response, 'background: rgba(15, 23, 42, 0.34) !important;')
        self.assertContains(response, '-webkit-backdrop-filter: blur(18px) saturate(1.16);')

    def test_custom_background_memakai_adaptive_contrast(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, 'html[data-bg="custom"] .surface-card')
        self.assertContains(response, 'background: rgba(255, 255, 255, 0.88) !important;')
        self.assertContains(response, 'html[data-theme="dark"][data-bg="custom"] .surface-card')
        self.assertContains(response, 'background: rgba(15, 23, 42, 0.78) !important;')
        self.assertContains(response, 'html[data-theme="dark"] main .text-slate-900')

    def test_sidebar_dark_mode_border_tidak_terlalu_terang(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, '--sidebar-active-border: rgba(94, 234, 212, 0.16);')
        self.assertContains(response, '--border-color: rgba(148, 163, 184, 0.20);')
        self.assertContains(response, 'html[data-theme="dark"] #dashboard-sidebar [class*="border-"]')
        self.assertContains(response, 'border-color: rgba(148, 163, 184, 0.10) !important;')
        self.assertContains(response, 'html[data-theme="dark"] #dashboard-sidebar [class*="ring-"]')
        self.assertContains(response, '--tw-ring-color: transparent !important;')
        self.assertContains(response, 'html[data-theme="dark"] #dashboard-sidebar [data-sidebar-submenu]')
        self.assertContains(response, 'border-color: rgba(148, 163, 184, 0.12) !important;')
        self.assertContains(response, 'html[data-theme="dark"] #dashboard-sidebar [data-sidebar-profile]')
        self.assertContains(response, 'border-color: rgba(148, 163, 184, 0.10) !important;')

    def test_scrollbar_dark_mode_global_tidak_terang(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, 'html[data-theme="dark"] *::-webkit-scrollbar')
        self.assertContains(response, 'html[data-theme="dark"] *::-webkit-scrollbar-track')
        self.assertContains(response, 'html[data-theme="dark"] *::-webkit-scrollbar-thumb')
        self.assertContains(response, 'scrollbar-color: rgba(71, 85, 105, 0.62) rgba(15, 23, 42, 0.24);')
        self.assertContains(response, 'html[data-theme="dark"] #dashboard-sidebar *::-webkit-scrollbar-thumb')
        self.assertContains(response, 'background: rgba(51, 65, 85, 0.60);')

    def test_table_hover_dark_mode_tidak_terang(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, 'html[data-theme="dark"] tbody tr:hover')
        self.assertContains(response, 'html[data-theme="dark"] tbody tr[class*="hover:bg-"]:hover')
        self.assertContains(response, 'background-color: rgba(30, 41, 59, 0.30) !important;')
        self.assertContains(response, 'html[data-theme="dark"] tbody tr:hover td')
        self.assertContains(response, 'html[data-theme="dark"] tbody tr:hover .text-slate-900')

    def test_touch_device_mengurangi_repaint_blur_dan_transisi(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, '@media (hover: none), (pointer: coarse)')
        self.assertContains(response, 'overscroll-behavior-y: contain;')
        self.assertContains(response, 'backface-visibility: hidden;')
        self.assertContains(response, 'body:has([data-app-content]) #dashboard-sidebar')
        self.assertContains(response, '[data-app-content] {')
        self.assertContains(response, 'animation: none !important;')
        self.assertContains(response, 'transition-duration: 0ms !important;')
        self.assertContains(response, 'will-change: auto !important;')
        self.assertContains(response, '[data-dashboard-sidebar-shell]')
        self.assertContains(response, 'transition: none !important;')

    def test_sidebar_touch_device_tidak_memakai_animasi_expand(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='User Sidebar Touch',
            nim_nik='0642201098',
            email='sidebar-touch@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567898',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, "const coarsePointerQuery = window.matchMedia('(hover: none), (pointer: coarse)');")
        self.assertContains(response, '&& !coarsePointerQuery.matches')
        self.assertContains(response, "coarsePointerQuery.matches ? '' : ' transition duration-150'")

    def test_date_input_calendar_icon_dark_mode_terlihat(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, 'html[data-theme="dark"] main input[type="date"]')
        self.assertContains(response, 'color-scheme: dark !important;')
        self.assertContains(response, '::-webkit-calendar-picker-indicator')
        self.assertContains(response, 'filter: invert(1) brightness(1.8) contrast(0.9) !important;')
        self.assertContains(response, 'dateInput.showPicker();')

    def test_confirmation_modal_mencegah_submit_sebelum_disetujui(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, "event.stopImmediatePropagation();")
        self.assertContains(response, "}, true);")
        self.assertContains(response, "const confirmedElement = pendingElement;")
        self.assertContains(response, "closeModal();")
        self.assertContains(response, "confirmedElement.requestSubmit();")

    def test_global_loading_overlay_untuk_request_async(self):
        response = self.client.get(reverse('pengguna:login'))

        self.assertContains(response, 'data-global-loading')
        self.assertContains(response, 'data-initial-loading="true"')
        self.assertContains(response, 'aria-hidden="false"')
        self.assertContains(response, 'data-global-loading-core')
        self.assertContains(response, 'labhub-loading-spin')
        self.assertContains(response, 'labhub-loading-float')
        self.assertContains(response, '[data-global-loading][data-initial-loading="true"]')
        self.assertContains(response, '--loading-bg-base')
        self.assertContains(response, 'linear-gradient(135deg, var(--loading-bg-base), var(--loading-bg-deep))')
        self.assertContains(response, '[data-global-loading]::before')
        self.assertContains(response, '[data-global-loading]::after')
        self.assertContains(response, 'labhub-loading-aura')
        self.assertContains(response, 'backdrop-filter: none;')
        self.assertNotContains(response, '[data-global-loading][data-loading-mode="action"]')
        self.assertContains(response, 'function hideInitialLoadingWhenReady()')
        self.assertContains(response, "window.addEventListener('load', hideInitialLoadingWhenReady, {once: true});")
        self.assertContains(response, 'function shouldSkipGlobalLoading(event)')
        self.assertContains(response, 'data-no-global-loading="true"')
        self.assertContains(response, "document.body.addEventListener('htmx:beforeRequest', showGlobalLoading);")
        self.assertContains(response, "document.body.addEventListener('htmx:afterRequest', hideGlobalLoading);")
        self.assertContains(response, "document.addEventListener('submit', function (event) {")
        self.assertContains(response, "document.addEventListener('click', function (event) {")
        self.assertContains(response, "event.target.closest('a[href]:not([target])")
        self.assertContains(response, "showGlobalLoading(event);")

    def test_navbar_notifikasi_merespons_event_realtime(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='User Notifikasi',
            nim_nik='0642201099',
            email='notifikasi@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567899',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'data-realtime-notification-trigger')
        self.assertContains(response, 'has-realtime-update')
        self.assertContains(response, "document.addEventListener('labhub:realtime'")
        self.assertContains(response, 'if (payload.silent) return;')
        self.assertContains(response, reverse('kalender:notifikasi_summary'))
        self.assertContains(response, 'syncNotificationSummary')
        self.assertContains(response, 'window.setInterval')
        self.assertContains(response, 'html[data-theme="dark"] .labhub-realtime-toast')
        self.assertContains(response, 'labhub-realtime-toast-title')
        self.assertContains(response, "window.addEventListener('focus', syncNotificationSummary);")
        self.assertContains(response, '}, 5000);')

    def test_logo_navbar_menyatu_dengan_panel_saat_scroll(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='User Navbar',
            nim_nik='0642201067',
            email='navbar@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567867',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, '.labhub-topbar.is-scrolled .labhub-topbar-brand')
        self.assertContains(response, 'background: transparent !important;')
        self.assertContains(response, 'border-color: transparent !important;')
        self.assertContains(response, '.labhub-topbar.is-scrolled .labhub-topbar-logo')

from apps.pengguna.models import Pengguna

from project_laboran.asgi import application

from .models import BugErrorLog, PercakapanBantuan, PesanBantuan
from .emails import send_branded_email


class BrandedEmailTests(TestCase):
    def test_email_memiliki_html_labhub_dan_fallback_teks(self):
        sent = send_branded_email(
            subject='Uji Email LabHub',
            recipients=['user@example.com'],
            text_body='Isi versi teks.',
            title='Notifikasi pengujian',
            intro='Ini adalah ringkasan notifikasi.',
            details=[{'label': 'Status', 'value': 'Berhasil'}],
            action_url='https://example.com/action',
            action_label='Buka LabHub',
        )

        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].body, 'Isi versi teks.')
        self.assertEqual(mail.outbox[0].alternatives[0][1], 'text/html')
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('LabHub', html)
        self.assertIn('Buka LabHub', html)
        self.assertIn('https://example.com/action', html)


class BantuanTests(TestCase):
    def setUp(self):
        self.mahasiswa = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Bantuan',
            nim_nik='0642201088',
            email='bantuan@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567888',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        self.login_as(self.mahasiswa)

    def login_as(self, pengguna):
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()

    def test_floating_chat_bantuan_muncul_setelah_login(self):
        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'data-help-floating')
        self.assertContains(response, 'data-help-dialog')
        self.assertContains(response, reverse('core:bantuan'))
        self.assertContains(response, reverse('core:bantuan_async_message'))
        self.assertContains(response, 'data-help-message-list')
        self.assertContains(response, 'data-help-form')
        self.assertContains(response, 'data-help-loading')
        self.assertContains(response, "event.key !== 'Enter' || event.shiftKey")
        self.assertContains(response, "fetch(asyncUrl")
        self.assertContains(response, 'Chat Bantuan')
        self.assertContains(response, '[data-help-floating] button')
        self.assertContains(response, 'background: rgba(15, 118, 110, 0.96) !important;')
        self.assertContains(response, 'html[data-theme="dark"] [data-help-floating] button')
        self.assertContains(response, 'background: rgba(20, 184, 166, 0.94) !important;')
        self.assertContains(response, '[data-help-dialog] > .surface-card')
        self.assertContains(response, 'background: rgba(255, 255, 255, 0.96) !important;')
        self.assertContains(response, 'html[data-theme="dark"] [data-help-dialog] > .surface-card')
        self.assertContains(response, 'background: rgba(15, 23, 42, 0.94) !important;')

    def test_floating_chat_bantuan_tidak_muncul_untuk_guest(self):
        self.client.session.flush()

        response = self.client.get(reverse('pengguna:login'))

        self.assertNotContains(response, 'data-help-floating')

    def test_admin_mendapat_floating_chat_dengan_jumlah_antrean(self):
        admin = Pengguna.objects.create(
            nama_pengguna='Admin Floating Chat',
            nim_nik='ADM-FLOATING-CHAT',
            email='admin-floating-chat@example.com',
            password='rahasia123',
            no_hp='081234567812',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='admin',
        )
        PercakapanBantuan.objects.create(pengguna=self.mahasiswa, status='admin')
        self.login_as(admin)

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'data-admin-chat-floating')
        self.assertContains(response, reverse('core:bantuan_admin'))
        self.assertContains(response, reverse('core:bantuan_admin_summary'))
        self.assertContains(response, 'data-admin-help-count')
        self.assertContains(response, 'updateAdminHelpSummary')
        self.assertContains(response, '[data-admin-chat-floating] > a')
        self.assertNotContains(response, 'data-help-dialog>')

    def test_admin_bantuan_summary_mengembalikan_jumlah_antrean(self):
        admin = Pengguna.objects.create(
            nama_pengguna='Admin Summary Chat',
            nim_nik='ADM-SUMMARY-CHAT',
            email='admin-summary-chat@example.com',
            password='rahasia123',
            no_hp='081234567813',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='admin',
        )
        PercakapanBantuan.objects.create(pengguna=self.mahasiswa, status='admin')
        PercakapanBantuan.objects.create(pengguna=self.mahasiswa, status='selesai')
        self.login_as(admin)

        response = self.client.get(reverse('core:bantuan_admin_summary'), HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['waiting_count'], 1)
        self.assertEqual(response.json()['label'], '1 mahasiswa bertanya')

    def test_bot_menjawab_pertanyaan_sederhana(self):
        response = self.client.post(reverse('core:bantuan'), {'pesan': 'Bagaimana cara daftar aslab?'})

        self.assertRedirects(response, reverse('core:bantuan'))
        conversation = PercakapanBantuan.objects.get(pengguna=self.mahasiswa)
        self.assertEqual(conversation.status, 'bot')
        self.assertTrue(conversation.pesan.filter(pengirim='bot', isi__icontains='transkrip').exists())

    def test_floating_chat_async_menjawab_tanpa_redirect(self):
        response = self.client.post(
            reverse('core:bantuan_async_message'),
            {'pesan': 'Bagaimana cara daftar aslab?'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        conversation = PercakapanBantuan.objects.get(pengguna=self.mahasiswa)
        self.assertEqual(conversation.status, 'bot')
        self.assertEqual(payload['conversation_status'], 'bot')
        self.assertEqual(payload['user_message']['content'], 'Bagaimana cara daftar aslab?')
        self.assertIn('transkrip', payload['bot_message']['content'])
        self.assertEqual(payload['help_url'], reverse('core:bantuan'))

    def test_halaman_bantuan_memakai_realtime_tanpa_full_loading(self):
        self.client.get(reverse('core:bantuan'))
        response = self.client.get(reverse('core:bantuan'))

        self.assertContains(response, 'data-chat-form')
        self.assertContains(response, 'data-no-global-loading="true"')
        self.assertContains(response, 'data-chat-loading')
        self.assertContains(response, 'data-chat-finished-notice')
        self.assertContains(response, "sendWithFetch(content)")
        self.assertContains(response, "event.key !== 'Enter' || event.shiftKey")
        self.assertContains(response, "payload.status === 'selesai'")
        self.assertContains(response, "switchToBotMode()")

    def test_bot_memahami_nilai_absensi_mahasiswa(self):
        self.client.post(reverse('core:bantuan'), {'pesan': 'Nilai realtime dan laporan itu gimana?'})

        conversation = PercakapanBantuan.objects.get(pengguna=self.mahasiswa)
        self.assertTrue(conversation.pesan.filter(pengirim='bot', isi__icontains='Nilai Realtime').exists())
        self.assertTrue(conversation.pesan.filter(pengirim='bot', isi__icontains='rata-rata').exists())

    def test_bot_memahami_import_peserta_csv(self):
        self.client.post(reverse('core:bantuan'), {'pesan': 'Peserta praktikum bisa import CSV?'})

        conversation = PercakapanBantuan.objects.get(pengguna=self.mahasiswa)
        self.assertTrue(conversation.pesan.filter(pengirim='bot', isi__icontains='import CSV').exists())
        self.assertTrue(conversation.pesan.filter(pengirim='bot', isi__icontains='NIM').exists())

    def test_bot_menampilkan_panduan_umum_web(self):
        self.client.post(reverse('core:bantuan'), {'pesan': 'Panduan fitur web LabHub apa saja?'})

        conversation = PercakapanBantuan.objects.get(pengguna=self.mahasiswa)
        self.assertTrue(conversation.pesan.filter(pengirim='bot', isi__icontains='Topik yang bisa saya bantu').exists())

    def test_pengguna_dapat_meneruskan_chat_ke_admin(self):
        self.client.get(reverse('core:bantuan'))

        response = self.client.post(reverse('core:bantuan_escalate'))

        self.assertRedirects(response, reverse('core:bantuan'))
        conversation = PercakapanBantuan.objects.get(pengguna=self.mahasiswa)
        self.assertEqual(conversation.status, 'admin')

    def test_non_admin_tidak_dapat_membuka_antrean_admin(self):
        response = self.client.get(reverse('core:bantuan_admin'))

        self.assertRedirects(response, reverse('core:bantuan'))

    def test_admin_dapat_membalas_chat_yang_dieskalasi(self):
        self.client.get(reverse('core:bantuan'))
        self.client.post(reverse('core:bantuan_escalate'))
        conversation = PercakapanBantuan.objects.get(pengguna=self.mahasiswa)
        admin = Pengguna.objects.create(
            nama_pengguna='Admin Bantuan',
            nim_nik='ADM-BANTUAN',
            email='admin-bantuan@example.com',
            password='rahasia123',
            no_hp='081234567889',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='admin',
        )
        self.login_as(admin)

        response = self.client.post(reverse('core:bantuan_admin'), {
            'percakapan': conversation.pk,
            'pesan': 'Silakan lengkapi CV pada profil terlebih dahulu.',
        })

        self.assertRedirects(response, f"{reverse('core:bantuan_admin')}?percakapan={conversation.pk}")
        self.assertTrue(conversation.pesan.filter(pengirim='admin', isi__icontains='lengkapi CV').exists())

    def test_halaman_admin_bantuan_selesai_memakai_websocket(self):
        self.client.get(reverse('core:bantuan'))
        self.client.post(reverse('core:bantuan_escalate'))
        conversation = PercakapanBantuan.objects.get(pengguna=self.mahasiswa)
        admin = Pengguna.objects.create(
            nama_pengguna='Admin Async Bantuan',
            nim_nik='ADM-ASYNC-BANTUAN',
            email='admin-async-bantuan@example.com',
            password='rahasia123',
            no_hp='081234567811',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='admin',
        )
        self.login_as(admin)

        response = self.client.get(f"{reverse('core:bantuan_admin')}?percakapan={conversation.pk}")

        self.assertContains(response, 'data-chat-finish')
        self.assertContains(response, "chatSocket.send(JSON.stringify({action: 'selesai'}));")
        self.assertContains(response, 'data-chat-finished-notice')
        self.assertContains(response, 'data-no-global-loading="true"')
        self.assertContains(response, 'help-admin-shell')
        self.assertContains(response, 'html[data-theme="dark"] .help-admin-shell')
        self.assertContains(response, 'data-chat-typing')
        self.assertContains(response, "action: 'typing'")
        self.assertContains(response, "action: 'presence'")
        self.assertContains(response, "event.key !== 'Enter' || event.shiftKey")
        self.assertContains(response, "form.requestSubmit();")

    def test_admin_settings_tidak_menampilkan_kartu_bantuan(self):
        admin = Pengguna.objects.create(
            nama_pengguna='Admin Pengaturan',
            nim_nik='ADM-SETTINGS',
            email='admin-settings@example.com',
            password='rahasia123',
            no_hp='081234567877',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='admin',
        )
        self.login_as(admin)

        response = self.client.get(reverse('core:settings'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<h3 class="mt-5 text-lg font-black tracking-tight text-slate-900">Bantuan</h3>', html=False)
        self.assertContains(response, 'Chat Bantuan Masuk')
        self.assertIn('Bug & Error List', [card['title'] for card in response.context['settings_cards']])

    def test_admin_dapat_membuka_bug_error_list(self):
        admin = Pengguna.objects.create(
            nama_pengguna='Admin Bug',
            nim_nik='ADM-BUG',
            email='admin-bug@example.com',
            password='rahasia123',
            no_hp='081234567871',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='admin',
        )
        BugErrorLog.objects.create(
            judul='Upload foto profil gagal',
            kategori='error',
            prioritas='tinggi',
            lokasi='/pengguna/1/edit-profil/',
            deskripsi='Folder media tidak ditemukan',
            dilaporkan_oleh=self.mahasiswa,
        )
        self.login_as(admin)

        response = self.client.get(reverse('core:bug_error_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bug & Error List')
        self.assertContains(response, 'Upload foto profil gagal')
        self.assertContains(response, 'Folder media tidak ditemukan')
        self.assertContains(response, 'Tambah Bug/Error')
        self.assertContains(response, 'bug-error-page')
        self.assertContains(response, 'html[data-theme="dark"] .bug-error-page .bug-error-card')
        self.assertContains(response, 'html[data-theme="dark"] .bug-error-page .bug-error-danger')
        self.assertContains(response, 'htmx.org')
        self.assertContains(response, 'data-bug-error-item-link')
        self.assertContains(response, 'data-bug-error-detail-panel')
        self.assertContains(response, "window.matchMedia('(max-width: 1279px)')")
        self.assertContains(response, 'detailPanel.scrollIntoView')
        self.assertContains(response, 'data-confirmation-modal')
        self.assertContains(response, 'data-confirm-message="Hapus bug/error Upload foto profil gagal? Data yang dihapus tidak dapat dikembalikan."')
        self.assertNotContains(response, 'hx-confirm')

    def test_bug_error_list_htmx_mengembalikan_partial(self):
        admin = Pengguna.objects.create(
            nama_pengguna='Admin Bug Async',
            nim_nik='ADM-BUG-ASYNC',
            email='admin-bug-async@example.com',
            password='rahasia123',
            no_hp='081234567867',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='admin',
        )
        BugErrorLog.objects.create(
            judul='Filter bug async',
            kategori='bug',
            prioritas='sedang',
            lokasi='/pengaturan/bug-error/',
            deskripsi='Daftar bug/error harus dapat diperbarui tanpa memuat ulang halaman penuh.',
            dilaporkan_oleh=admin,
        )
        self.login_as(admin)

        response = self.client.get(reverse('core:bug_error_list'), HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="bug-error-page-content"', html=False)
        self.assertContains(response, 'hx-get=')
        self.assertContains(response, 'hx-post=')
        self.assertContains(response, 'Filter bug async')
        self.assertNotContains(response, '<html')

    def test_non_admin_tidak_dapat_membuka_bug_error_list(self):
        response = self.client.get(reverse('core:bug_error_list'))

        self.assertRedirects(response, reverse('dashboard:home'))

    def test_laboran_dapat_mengambil_bug_error_yang_belum_ditangani(self):
        laboran = Pengguna.objects.create(
            nama_pengguna='Laboran Bug',
            nim_nik='LAB-BUG',
            email='laboran-bug@example.com',
            password='rahasia123',
            no_hp='081234567874',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        log = BugErrorLog.objects.create(
            judul='Sidebar dark mode terlalu terang',
            kategori='ui',
            prioritas='sedang',
            lokasi='/jadwal/',
            deskripsi='Item sidebar terlihat putih saat ditekan.',
            dilaporkan_oleh=self.mahasiswa,
        )
        self.login_as(laboran)

        response = self.client.post(reverse('core:bug_error_list'), {
            'action': 'claim',
            'log_id': log.pk,
        })

        self.assertRedirects(response, f"{reverse('core:bug_error_list')}?log={log.pk}")
        log.refresh_from_db()
        self.assertEqual(log.ditangani_oleh, laboran)
        self.assertEqual(log.status, BugErrorLog.STATUS_DIPROSES)

    def test_laboran_lain_tidak_dapat_mengambil_bug_error_yang_sudah_ditangani(self):
        laboran_awal = Pengguna.objects.create(
            nama_pengguna='Laboran Awal',
            nim_nik='LAB-AWAL',
            email='laboran-awal@example.com',
            password='rahasia123',
            no_hp='081234567875',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        laboran_lain = Pengguna.objects.create(
            nama_pengguna='Laboran Lain',
            nim_nik='LAB-LAIN',
            email='laboran-lain@example.com',
            password='rahasia123',
            no_hp='081234567876',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='laboran',
        )
        log = BugErrorLog.objects.create(
            judul='Filter status nyaru',
            kategori='ui',
            prioritas='rendah',
            lokasi='/pengaturan/bug-error/',
            deskripsi='Select box status kurang terlihat.',
            ditangani_oleh=laboran_awal,
            status=BugErrorLog.STATUS_DIPROSES,
        )
        self.login_as(laboran_lain)

        response = self.client.post(reverse('core:bug_error_list'), {
            'action': 'claim',
            'log_id': log.pk,
        })

        self.assertRedirects(response, f"{reverse('core:bug_error_list')}?log={log.pk}")
        log.refresh_from_db()
        self.assertEqual(log.ditangani_oleh, laboran_awal)

    def test_laboran_dapat_menyelesaikan_bug_error_yang_dia_tangani(self):
        laboran = Pengguna.objects.create(
            nama_pengguna='Laboran Penyelesai',
            nim_nik='LAB-SELESAI',
            email='laboran-selesai@example.com',
            password='rahasia123',
            no_hp='081234567870',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        log = BugErrorLog.objects.create(
            judul='Bug sudah diperbaiki',
            kategori='bug',
            prioritas='sedang',
            lokasi='/pengaturan/bug-error/',
            deskripsi='Bug ini sedang ditangani laboran.',
            ditangani_oleh=laboran,
            status=BugErrorLog.STATUS_DIPROSES,
        )
        self.login_as(laboran)

        response = self.client.post(reverse('core:bug_error_list'), {
            'action': 'complete',
            'log_id': log.pk,
        })

        self.assertRedirects(response, f"{reverse('core:bug_error_list')}?log={log.pk}")
        log.refresh_from_db()
        self.assertEqual(log.status, BugErrorLog.STATUS_SELESAI)

    def test_laboran_tidak_dapat_menyelesaikan_bug_error_milik_laboran_lain(self):
        laboran_awal = Pengguna.objects.create(
            nama_pengguna='Laboran Pemilik',
            nim_nik='LAB-PEMILIK',
            email='laboran-pemilik@example.com',
            password='rahasia123',
            no_hp='081234567869',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        laboran_lain = Pengguna.objects.create(
            nama_pengguna='Laboran Bukan Pemilik',
            nim_nik='LAB-BUKAN-PEMILIK',
            email='laboran-bukan-pemilik@example.com',
            password='rahasia123',
            no_hp='081234567868',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='laboran',
        )
        log = BugErrorLog.objects.create(
            judul='Bug milik laboran lain',
            kategori='bug',
            prioritas='tinggi',
            lokasi='/dashboard/',
            deskripsi='Bug ini tidak boleh diselesaikan laboran lain.',
            ditangani_oleh=laboran_awal,
            status=BugErrorLog.STATUS_DIPROSES,
        )
        self.login_as(laboran_lain)

        response = self.client.post(reverse('core:bug_error_list'), {
            'action': 'complete',
            'log_id': log.pk,
        })

        self.assertRedirects(response, f"{reverse('core:bug_error_list')}?log={log.pk}")
        log.refresh_from_db()
        self.assertEqual(log.status, BugErrorLog.STATUS_DIPROSES)

    def test_admin_menambahkan_bug_error_manual(self):
        admin = Pengguna.objects.create(
            nama_pengguna='Admin Manual Bug',
            nim_nik='ADM-MANUAL-BUG',
            email='admin-manual-bug@example.com',
            password='rahasia123',
            no_hp='081234567872',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='admin',
        )
        self.login_as(admin)

        response = self.client.post(reverse('core:bug_error_list'), {
            'action': 'create',
            'judul': 'Modal profil terlalu terang',
            'kategori': 'ui',
            'prioritas': 'sedang',
            'lokasi': '/pengguna/1/',
            'deskripsi': 'Beberapa input masih kurang kontras saat dark mode.',
            'langkah_reproduksi': 'Buka profil, aktifkan dark mode, klik edit.',
            'hasil_aktual': 'Input tanggal sulit terlihat.',
            'ekspektasi': 'Ikon dan border terlihat jelas.',
        })

        log = BugErrorLog.objects.get(judul='Modal profil terlalu terang')
        self.assertRedirects(response, f"{reverse('core:bug_error_list')}?log={log.pk}")
        self.assertEqual(log.dilaporkan_oleh, admin)
        self.assertEqual(log.kategori, 'ui')

    def test_admin_dapat_menghapus_bug_error_manual(self):
        admin = Pengguna.objects.create(
            nama_pengguna='Admin Hapus Bug',
            nim_nik='ADM-HAPUS-BUG',
            email='admin-hapus-bug@example.com',
            password='rahasia123',
            no_hp='081234567873',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='admin',
        )
        log = BugErrorLog.objects.create(
            judul='Catatan bug duplikat',
            kategori='bug',
            prioritas='rendah',
            lokasi='/pengaturan/bug-error/',
            deskripsi='Catatan ini perlu dihapus.',
            dilaporkan_oleh=admin,
        )
        self.login_as(admin)

        response = self.client.post(reverse('core:bug_error_list'), {
            'action': 'delete',
            'log_id': log.pk,
        })

        self.assertRedirects(response, reverse('core:bug_error_list'))
        self.assertFalse(BugErrorLog.objects.filter(pk=log.pk).exists())

    def test_settings_tidak_menampilkan_kartu_pendaftaran_aslab(self):
        laboran = Pengguna.objects.create(
            nama_pengguna='Laboran Pengaturan',
            nim_nik='LAB-SETTINGS',
            email='laboran-settings@example.com',
            password='rahasia123',
            no_hp='081234567876',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        self.login_as(laboran)

        response = self.client.get(reverse('core:settings'))

        self.assertEqual(response.status_code, 200)
        card_titles = [card['title'] for card in response.context['settings_cards']]
        self.assertNotIn('Pendaftaran Aslab', card_titles)
        self.assertIn('Pengguna', card_titles)

    def test_tampilan_disimpan_otomatis_ke_akun_tanpa_tombol_simpan(self):
        response = self.client.get(reverse('core:settings'))
        self.assertNotContains(response, 'Simpan Tampilan')
        self.assertContains(response, 'Tersimpan otomatis')

        response = self.client.post(reverse('core:settings'), {
            'theme_mode': 'dark',
            'background_mode': 'lab',
            'hapus_background': '',
        })

        self.assertRedirects(response, reverse('core:settings'))
        self.mahasiswa.refresh_from_db()
        self.assertEqual(self.mahasiswa.theme_mode, 'dark')
        self.assertEqual(self.mahasiswa.background_mode, 'lab')


class BantuanWebSocketTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.mahasiswa = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Socket',
            nim_nik='0642201099',
            email='socket@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567899',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        self.admin = Pengguna.objects.create(
            nama_pengguna='Admin Socket',
            nim_nik='ADM-SOCKET',
            email='admin-socket@example.com',
            password='rahasia123',
            no_hp='081234567800',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='admin',
        )
        self.conversation = PercakapanBantuan.objects.create(
            pengguna=self.mahasiswa,
            status='admin',
        )

    def session_headers(self, pengguna):
        session = SessionStore()
        session['pengguna_id'] = pengguna.pk
        session.save()
        return [(b'cookie', f'{settings.SESSION_COOKIE_NAME}={session.session_key}'.encode())]

    def test_pengguna_menerima_pesan_admin_via_websocket(self):
        user_headers = self.session_headers(self.mahasiswa)
        admin_headers = self.session_headers(self.admin)

        async def scenario():
            user_socket = WebsocketCommunicator(
                application,
                f'/ws/bantuan/{self.conversation.pk}/',
                headers=user_headers,
            )
            admin_socket = WebsocketCommunicator(
                application,
                f'/ws/bantuan/{self.conversation.pk}/',
                headers=admin_headers,
            )
            user_connected, _ = await user_socket.connect()
            admin_connected, _ = await admin_socket.connect()
            self.assertTrue(user_connected)
            self.assertTrue(admin_connected)

            await admin_socket.send_json_to({'pesan': 'Halo, ada yang bisa dibantu?'})
            payload = await user_socket.receive_json_from()

            self.assertEqual(payload['type'], 'message')
            self.assertEqual(payload['message']['pengirim'], 'admin')
            self.assertEqual(payload['message']['isi'], 'Halo, ada yang bisa dibantu?')

            await user_socket.disconnect()
            await admin_socket.disconnect()

        async_to_sync(scenario)()
        self.assertTrue(PesanBantuan.objects.filter(percakapan=self.conversation, pengirim='admin').exists())

    def test_admin_menyelesaikan_percakapan_via_websocket(self):
        user_headers = self.session_headers(self.mahasiswa)
        admin_headers = self.session_headers(self.admin)

        async def scenario():
            user_socket = WebsocketCommunicator(
                application,
                f'/ws/bantuan/{self.conversation.pk}/',
                headers=user_headers,
            )
            admin_socket = WebsocketCommunicator(
                application,
                f'/ws/bantuan/{self.conversation.pk}/',
                headers=admin_headers,
            )
            user_connected, _ = await user_socket.connect()
            admin_connected, _ = await admin_socket.connect()
            self.assertTrue(user_connected)
            self.assertTrue(admin_connected)

            await admin_socket.send_json_to({'action': 'selesai'})
            payload = await user_socket.receive_json_from()

            self.assertEqual(payload['type'], 'status')
            self.assertEqual(payload['status'], 'selesai')
            self.assertEqual(payload['status_label'], 'Selesai')

            await user_socket.disconnect()
            await admin_socket.disconnect()

        async_to_sync(scenario)()
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.status, 'selesai')

    def test_typing_dan_presence_dikirim_via_websocket(self):
        user_headers = self.session_headers(self.mahasiswa)
        admin_headers = self.session_headers(self.admin)

        async def scenario():
            user_socket = WebsocketCommunicator(
                application,
                f'/ws/bantuan/{self.conversation.pk}/',
                headers=user_headers,
            )
            admin_socket = WebsocketCommunicator(
                application,
                f'/ws/bantuan/{self.conversation.pk}/',
                headers=admin_headers,
            )
            user_connected, _ = await user_socket.connect()
            admin_connected, _ = await admin_socket.connect()
            self.assertTrue(user_connected)
            self.assertTrue(admin_connected)

            await admin_socket.send_json_to({'action': 'presence', 'state': 'online'})
            presence_payload = await user_socket.receive_json_from()
            self.assertEqual(presence_payload['type'], 'presence')
            self.assertEqual(presence_payload['sender_role'], 'admin')
            self.assertEqual(presence_payload['state'], 'online')

            await user_socket.send_json_to({'action': 'typing', 'is_typing': True})
            typing_payload = await admin_socket.receive_json_from()
            self.assertEqual(typing_payload['type'], 'typing')
            self.assertEqual(typing_payload['sender_role'], 'mahasiswa')
            self.assertTrue(typing_payload['is_typing'])

            await user_socket.disconnect()
            await admin_socket.disconnect()

        async_to_sync(scenario)()

    def test_pengguna_tidak_bisa_membuka_percakapan_orang_lain(self):
        pengguna_lain = Pengguna.objects.create(
            nama_pengguna='User Lain',
            nim_nik='0642201100',
            email='lain@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567811',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        headers = self.session_headers(pengguna_lain)

        async def scenario():
            communicator = WebsocketCommunicator(
                application,
                f'/ws/bantuan/{self.conversation.pk}/',
                headers=headers,
            )
            connected, _ = await communicator.connect()
            self.assertFalse(connected)

        async_to_sync(scenario)()
