from datetime import date, time, timedelta

from django.test import TestCase
from django.urls import reverse

from apps.pengguna.models import Pengguna

from .models import KegiatanKalender
from .utils import get_perayaan_notifications


class KalenderViewsTests(TestCase):
    def setUp(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='Lab Admin',
            nim_nik='ADM-KALENDER',
            email='admin-kalender@example.com',
            password='rahasia123',
            no_hp='081234567801',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='admin',
        )
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()

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
        self.assertContains(response, 'Hari Kemerdekaan Republik Indonesia')
        self.assertContains(response, 'Tahun Baru Imlek')
        self.assertContains(response, 'Peringatan Tragedi Trisakti')
        self.assertContains(response, 'Dies Natalis Universitas Trisakti')

    def test_notifikasi_page_loads(self):
        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notifikasi Kegiatan')

    def test_perayaan_otomatis_masuk_notifikasi(self):
        notifications = get_perayaan_notifications(date(2026, 8, 15), days=7)

        titles = [notification['judul'] for notification in notifications]
        self.assertIn('Hari Kemerdekaan Republik Indonesia', titles)

