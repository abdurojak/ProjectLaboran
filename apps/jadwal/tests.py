from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from .models import JadwalPraktikum


class JadwalViewTests(TestCase):
    def setUp(self):
        JadwalPraktikum.objects.create(
            mata_praktikum='Praktikum Basis Data',
            kelas='XI RPL 1',
            ruangan='Lab Rekayasa Data',
            pengampu='Ibu Sari',
            tanggal=date(2026, 6, 18),
            waktu_mulai=time(8, 0),
            waktu_selesai=time(10, 0),
        )

    def test_jadwal_page_loads(self):
        response = self.client.get(reverse('jadwal:jadwal_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jadwal Praktikum')

