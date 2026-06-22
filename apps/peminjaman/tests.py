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
        self.barang_lain = Barang.objects.create(
            nama='Mikroskop',
            kode_barang='LAB-002',
            jumlah=10,
            lokasi=self.lokasi,
            kondisi='baik',
        )
        self.barang_tersedia_lain = Barang.objects.create(
            nama='Mikroskop',
            kode_barang='LAB-004',
            jumlah=10,
            lokasi=self.lokasi,
            kondisi='baik',
        )
        self.barang_rusak = Barang.objects.create(
            nama='Mikroskop',
            kode_barang='LAB-003',
            jumlah=10,
            lokasi=self.lokasi,
            kondisi='rusak_ringan',
        )
        self.barang_rusak_berat = Barang.objects.create(
            nama='Mikroskop',
            kode_barang='LAB-005',
            jumlah=10,
            lokasi=self.lokasi,
            kondisi='rusak_berat',
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

    def test_list_page_memakai_modal_konfirmasi_hapus(self):
        response = self.client.get(reverse('peminjaman:peminjaman_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-confirmation-modal')
        self.assertContains(response, 'data-confirmation-trigger')
        self.assertContains(response, 'Lanjut ke halaman konfirmasi hapus peminjaman Andi Pratama?')
        self.assertContains(response, reverse('peminjaman:peminjaman_delete', args=[self.peminjaman.pk]))

    def test_detail_page_loads(self):
        response = self.client.get(reverse('peminjaman:peminjaman_detail', args=[self.peminjaman.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Andi Pratama')
        self.assertContains(response, '2201001')
        self.assertContains(response, '081234567890')

    def test_detail_page_memakai_modal_konfirmasi_hapus(self):
        response = self.client.get(reverse('peminjaman:peminjaman_detail', args=[self.peminjaman.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-confirmation-modal')
        self.assertContains(response, 'data-confirmation-trigger')
        self.assertContains(response, 'Lanjut ke halaman konfirmasi hapus peminjaman Andi Pratama?')

    def test_create_menolak_detail_barang_rusak_berat(self):
        response = self.client.post(
            reverse('peminjaman:peminjaman_create'),
            {
                'selected_barang_ids': str(self.barang_rusak_berat.pk),
                'nama_peminjam': 'Budi',
                'nim': '2201002',
                'no_hp': '081111111111',
                'jumlah': 1,
                'tanggal_pinjam': '2026-06-21',
                'tanggal_kembali': '2026-06-22',
                'status': 'diajukan',
                'catatan': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pilih minimal satu detail barang yang tersedia dan tidak rusak berat.')
        self.assertFalse(PeminjamanAlat.objects.filter(nama_peminjam='Budi').exists())


    def test_form_peminjaman_memakai_dialog_pencarian_detail_barang(self):
        response = self.client.get(reverse('peminjaman:peminjaman_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-selected-barang-list')
        self.assertContains(response, 'data-selected-barang-empty')
        self.assertContains(response, 'data-barang-picker-open')
        self.assertContains(response, f'{self.barang.kode_barang} - {self.barang.nama}')
        self.assertContains(response, 'name="selected_barang_ids"')
        self.assertContains(response, 'data-barang-picker-done')
        self.assertNotContains(response, '<select name="barang"')
        self.assertNotContains(response, 'id="id_barang_display"')

    def test_form_edit_menampilkan_detail_barang_terpilih_sebagai_badge(self):
        response = self.client.get(reverse('peminjaman:peminjaman_update', args=[self.peminjaman.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-selected-barang-id="{self.barang.pk}"')
        self.assertContains(response, f'{self.barang.kode_barang} - {self.barang.nama}')
        self.assertContains(response, 'data-selected-barang-remove')

    def test_barang_dipinjam_dan_rusak_berat_tidak_bisa_dipilih(self):
        response = self.client.get(reverse('peminjaman:peminjaman_create'))

        self.assertContains(response, self.barang.kode_barang)
        self.assertContains(response, self.barang_rusak.kode_barang)
        self.assertContains(response, self.barang_rusak_berat.kode_barang)
        self.assertContains(response, 'data-barang-disabled="true"', count=2)

    def test_kondisi_barang_di_dialog_memakai_warna_teks(self):
        response = self.client.get(reverse('peminjaman:peminjaman_create'))

        self.assertContains(response, 'text-emerald-700')
        self.assertContains(response, 'text-amber-700')
        self.assertContains(response, 'text-rose-700')

    def test_create_multiple_detail_barang_membuat_beberapa_peminjaman(self):
        response = self.client.post(
            reverse('peminjaman:peminjaman_create'),
            {
                'selected_barang_ids': f'{self.barang_rusak.pk},{self.barang_lain.pk}',
                'nama_peminjam': 'Budi',
                'nim': '2201002',
                'no_hp': '081111111111',
                'jumlah': 2,
                'tanggal_pinjam': '2026-06-21',
                'tanggal_kembali': '2026-06-22',
                'status': 'diajukan',
                'catatan': '',
            },
        )

        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        peminjaman = PeminjamanAlat.objects.filter(nama_peminjam='Budi').order_by('barang__kode_barang')
        self.assertEqual(peminjaman.count(), 2)
        self.assertEqual([item.barang for item in peminjaman], [self.barang_lain, self.barang_rusak])
        self.assertEqual([item.jumlah for item in peminjaman], [1, 1])

    def test_create_menolak_detail_barang_yang_sedang_dipinjam(self):
        response = self.client.post(
            reverse('peminjaman:peminjaman_create'),
            {
                'selected_barang_ids': str(self.barang.pk),
                'nama_peminjam': 'Budi',
                'nim': '2201002',
                'no_hp': '081111111111',
                'jumlah': 1,
                'tanggal_pinjam': '2026-06-21',
                'tanggal_kembali': '2026-06-22',
                'status': 'diajukan',
                'catatan': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pilih minimal satu detail barang yang tersedia dan tidak rusak berat.')
        self.assertFalse(PeminjamanAlat.objects.filter(nama_peminjam='Budi').exists())


class PeminjamanAlatModelTests(TestCase):
    def test_kode_pinjam_dibuat_dari_tanggal_pinjam_dan_id(self):
        lokasi = Lokasi.objects.create(nama_lokasi='Gudang A')
        barang = Barang.objects.create(
            nama='Mikroskop',
            kode_barang='LAB-001',
            jumlah=10,
            lokasi=lokasi,
            kondisi='baik',
        )

        peminjaman = PeminjamanAlat.objects.create(
            barang=barang,
            nama_peminjam='Andi Pratama',
            jumlah=1,
            tanggal_pinjam=date(2026, 6, 22),
            tanggal_kembali=date(2026, 6, 23),
        )

        self.assertEqual(peminjaman.kode_pinjam, f'PJM-260622-{peminjaman.id:04d}')
