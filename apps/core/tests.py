from django.test import TestCase
from django.urls import reverse

from apps.pengguna.models import Pengguna

from .models import PercakapanBantuan


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
