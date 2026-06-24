from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.pengguna.models import Pengguna

from .models import Asleb, HonorAsleb


class AslebViewTests(TestCase):
    def setUp(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='Lab Admin',
            nim_nik='ADM-ASLEB',
            email='admin-asleb@example.com',
            password='rahasia123',
            no_hp='081234567800',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='admin',
        )
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()

        self.asleb = Asleb.objects.create(
            nama='Siti Nurhaliza',
            nim='2301001',
            no_hp='081234567890',
            email='siti@example.com',
            program_studi='Rekayasa Perangkat Lunak',
            matkul='Pemrograman Web',
            semester=4,
            tanggal_bergabung=date(2026, 6, 22),
        )

    def test_asleb_list_page_loads(self):
        response = self.client.get(reverse('asleb:asleb_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Data Asleb')
        self.assertContains(response, 'Siti Nurhaliza')
        self.assertContains(response, 'Pemrograman Web')

    def test_asleb_search_filters_data(self):
        response = self.client.get(reverse('asleb:asleb_list'), {'q': '2301001'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Siti Nurhaliza')

    def test_asleb_search_filters_by_matkul(self):
        response = self.client.get(reverse('asleb:asleb_list'), {'q': 'Pemrograman Web'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Siti Nurhaliza')

    def test_honor_asleb_mengikuti_rumus_excel(self):
        honor = HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 4, 1),
            level='senior',
            jumlah_praktikum=2,
            total_pertemuan=10,
            pic_transfer='Faiz',
            status='diproses',
        )

        self.assertEqual(honor.total_jam_terealisasi, 70)
        self.assertEqual(honor.total_akhir, 60)
        self.assertEqual(honor.honor_per_jam, 8000)
        self.assertEqual(honor.jumlah, 480000)

    def test_honor_list_page_loads(self):
        HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 4, 1),
            level='junior',
            jumlah_praktikum=1,
            total_pertemuan=3,
            pic_transfer='Faiz',
            status='diproses',
        )

        response = self.client.get(reverse('asleb:honor_list'), {'bulan': '2026-04'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rekap Honorarium Asleb')
        self.assertContains(response, 'Siti Nurhaliza')
        self.assertContains(response, 'Rp 147.000')
