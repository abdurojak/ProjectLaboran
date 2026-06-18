from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.inventaris.models import Barang, Lokasi
from .models import PeminjamanAlat


class PeminjamanViewsTests(TestCase):
    def setUp(self):
        self.lokasi = Lokasi.objects.create(nama_lokasi='Gudang A')
        self.barang = Barang.objects.create(
            nama='Mikroskop',
            kode_barang='LAB-001',
            jumlah=10,
            lokasi=self.lokasi,
            kondisi='baik',
        )
        self.peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Andi Pratama',
            nim='2201001',
            no_hp='081234567890',
            jumlah=2,
            tanggal_pinjam=date(2026, 6, 18),
            tanggal_kembali=date(2026, 6, 20),
            status='dipinjam',
        )

    def test_list_page_loads(self):
        response = self.client.get(reverse('peminjaman:peminjaman_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Peminjaman Alat')

    def test_detail_page_loads(self):
        response = self.client.get(reverse('peminjaman:peminjaman_detail', args=[self.peminjaman.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Andi Pratama')
        self.assertContains(response, '2201001')
        self.assertContains(response, '081234567890')
