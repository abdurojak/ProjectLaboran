from django.test import TestCase
from django.urls import reverse

from apps.pengguna.models import Pengguna


class RuanganViewTests(TestCase):
    def setUp(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='Lab Admin',
            nim_nik='ADM-RUANGAN',
            email='admin-ruangan@example.com',
            password='rahasia123',
            no_hp='081234567801',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()

    def test_ruangan_page_loads(self):
        response = self.client.get(reverse('ruangan:ruangan_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lab Rekayasa Perangkat Lunak')

