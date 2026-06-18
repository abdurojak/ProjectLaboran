from datetime import date, time, timedelta

from django.test import TestCase
from django.urls import reverse

from .models import KegiatanKalender


class KalenderViewsTests(TestCase):
    def setUp(self):
        KegiatanKalender.objects.create(
            judul='Praktikum Jaringan',
            tanggal=date.today() + timedelta(days=1),
            waktu_mulai=time(9, 0),
            waktu_selesai=time(11, 0),
            lokasi='Lab Sistem Keamanan Informasi',
            tampilkan_notifikasi=True,
        )

    def test_kalender_page_loads(self):
        response = self.client.get(reverse('kalender:kegiatan_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kalender Kegiatan')

    def test_notifikasi_page_loads(self):
        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notifikasi Kegiatan')

