from django.test import TestCase
from django.urls import reverse

from .models import Barang, Lokasi


class LokasiModelTests(TestCase):
    def test_kode_lokasi_dibuat_dari_id_database(self):
        lokasi = Lokasi.objects.create(nama_lokasi='Lab Kimia')

        self.assertEqual(lokasi.kode_lokasi, f'LK{lokasi.id:06d}')
        self.assertEqual(len(lokasi.kode_lokasi), 8)


class LokasiViewTests(TestCase):
    def test_tambah_lokasi_tidak_meminta_kode_lokasi(self):
        response = self.client.get(reverse('inventaris:lokasi_create'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="kode_lokasi"')


class BarangLokasiTests(TestCase):
    def test_form_barang_memakai_pilihan_dari_tabel_lokasi(self):
        lokasi = Lokasi.objects.create(nama_lokasi='Lab Fisika')

        response = self.client.get(reverse('inventaris:barang_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, lokasi.nama_lokasi)

    def test_daftar_barang_menampilkan_nama_lokasi_dari_relasi(self):
        lokasi = Lokasi.objects.create(nama_lokasi='Ruang Alat')
        Barang.objects.create(
            nama='Mikroskop',
            kode_barang='BRG001',
            jumlah=2,
            lokasi=lokasi,
        )

        response = self.client.get(reverse('inventaris:barang_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ruang Alat')


class BarangModelTests(TestCase):
    def test_kode_barang_generated_automatically(self):
        lokasi = Lokasi.objects.create(nama_lokasi='Lab Pemrograman')
        barang = Barang.objects.create(
            nama='Keyboard',
            jumlah=5,
            lokasi=lokasi,
            kondisi='baik',
        )

        self.assertEqual(barang.kode_barang, 'LAB-0001')


class BarangListViewTests(TestCase):
    def setUp(self):
        self.lab_pemrograman = Lokasi.objects.create(nama_lokasi='Lab Pemrograman')
        self.lab_ski = Lokasi.objects.create(nama_lokasi='Lab Sistem Keamanan Informasi')
        Barang.objects.create(
            nama='Keyboard',
            jumlah=5,
            lokasi=self.lab_pemrograman,
            kondisi='baik',
        )
        Barang.objects.create(
            nama='Router',
            jumlah=2,
            lokasi=self.lab_ski,
            kondisi='rusak_ringan',
        )

    def test_search_filters_barang(self):
        response = self.client.get(reverse('inventaris:barang_list'), {'q': 'Router'})

        self.assertContains(response, 'Router')
        self.assertNotContains(response, 'Keyboard')

    def test_kondisi_filter_filters_barang(self):
        response = self.client.get(reverse('inventaris:barang_list'), {'kondisi': 'baik'})

        self.assertContains(response, 'Keyboard')
        self.assertNotContains(response, 'Router')

    def test_lokasi_filter_filters_barang(self):
        response = self.client.get(reverse('inventaris:barang_list'), {'lokasi': self.lab_ski.id})

        self.assertContains(response, 'Router')
        self.assertNotContains(response, 'Keyboard')
