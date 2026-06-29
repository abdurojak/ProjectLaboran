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

from apps.pengguna.models import Pengguna

from project_laboran.asgi import application

from .models import PercakapanBantuan, PesanBantuan
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
        self.assertContains(response, 'Chat Bantuan')

    def test_floating_chat_bantuan_tidak_muncul_untuk_guest(self):
        self.client.session.flush()

        response = self.client.get(reverse('pengguna:login'))

        self.assertNotContains(response, 'data-help-floating')

    def test_bot_menjawab_pertanyaan_sederhana(self):
        response = self.client.post(reverse('core:bantuan'), {'pesan': 'Bagaimana cara daftar aslab?'})

        self.assertRedirects(response, reverse('core:bantuan'))
        conversation = PercakapanBantuan.objects.get(pengguna=self.mahasiswa)
        self.assertEqual(conversation.status, 'bot')
        self.assertTrue(conversation.pesan.filter(pengirim='bot', isi__icontains='transkrip').exists())

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
