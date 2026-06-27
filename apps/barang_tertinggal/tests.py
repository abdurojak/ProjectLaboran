from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from .models import BarangTertinggal


class BarangTertinggalViewTests(TestCase):
    def setUp(self):
        self.barang = BarangTertinggal.objects.create(
            nama_barang='Flashdisk',
            jenis_barang='Elektronik',
            jumlah_barang=1,
            tanggal_ditemukan='2026-06-22',
        )

    def test_page_loads(self):
        response = self.client.get(reverse('barang_tertinggal:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Barang Mahasiswa Tertinggal')

    def test_list_menampilkan_data_dan_modal_konfirmasi(self):
        response = self.client.get(reverse('barang_tertinggal:list'))

        self.assertContains(response, self.barang.kode_barang_tertinggal)
        self.assertContains(response, 'Flashdisk')
        self.assertContains(response, 'Tertinggal')
        self.assertContains(response, 'Rusak')
        self.assertContains(response, 'Hilang')
        self.assertContains(response, 'data-confirmation-modal')
        self.assertContains(response, reverse('barang_tertinggal:delete', args=[self.barang.pk]))

    def test_create_barang_tertinggal(self):
        foto = SimpleUploadedFile(
            'botol.gif',
            b'GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;',
            content_type='image/gif',
        )
        response = self.client.post(
            reverse('barang_tertinggal:create'),
            {
                'nama_barang': 'Botol Minum',
                'jenis_barang': 'Perlengkapan',
                'jumlah_barang': 1,
                'tanggal_ditemukan': '2026-06-23',
                'tanggal_diambil': '',
                'nama_pemilik': '',
                'status': 'tertinggal',
                'foto': foto,
            },
        )

        barang = BarangTertinggal.objects.get(nama_barang='Botol Minum')
        self.assertRedirects(response, reverse('barang_tertinggal:list'))
        self.assertEqual(barang.kode_barang_tertinggal, f'BRT-260623-{barang.id:04d}')
        self.assertTrue(barang.foto)

    def test_update_barang_tertinggal(self):
        response = self.client.post(
            reverse('barang_tertinggal:update', args=[self.barang.pk]),
            {
                'nama_barang': 'Flashdisk Sandisk',
                'jenis_barang': 'Elektronik',
                'jumlah_barang': 1,
                'tanggal_ditemukan': '2026-06-22',
                'tanggal_diambil': '2026-06-24',
                'nama_pemilik': 'Andi',
                'status': 'diambil',
            },
        )

        self.barang.refresh_from_db()
        self.assertRedirects(response, reverse('barang_tertinggal:list'))
        self.assertEqual(self.barang.nama_barang, 'Flashdisk Sandisk')
        self.assertEqual(self.barang.status, 'diambil')

    def test_form_edit_bisa_menghapus_foto(self):
        self.barang.foto = SimpleUploadedFile('flashdisk.jpg', b'fake-image-content', content_type='image/jpeg')
        self.barang.save()

        response = self.client.post(
            reverse('barang_tertinggal:update', args=[self.barang.pk]),
            {
                'nama_barang': 'Flashdisk',
                'jenis_barang': 'Elektronik',
                'jumlah_barang': 1,
                'tanggal_ditemukan': '2026-06-22',
                'tanggal_diambil': '',
                'nama_pemilik': '',
                'status': 'tertinggal',
                'hapus_foto': '1',
            },
        )

        self.barang.refresh_from_db()
        self.assertRedirects(response, reverse('barang_tertinggal:list'))
        self.assertFalse(self.barang.foto)

    def test_delete_barang_tertinggal(self):
        response = self.client.post(reverse('barang_tertinggal:delete', args=[self.barang.pk]))

        self.assertRedirects(response, reverse('barang_tertinggal:list'))
        self.assertFalse(BarangTertinggal.objects.filter(pk=self.barang.pk).exists())


class BarangTertinggalModelTests(TestCase):
    def test_kode_barang_tertinggal_dibuat_dari_tanggal_ditemukan_dan_id(self):
        barang = BarangTertinggal.objects.create(
            nama_barang='Kalkulator',
            jenis_barang='Elektronik',
            jumlah_barang=1,
            tanggal_ditemukan='2026-06-22',
        )

        self.assertEqual(barang.kode_barang_tertinggal, f'BRT-260622-{barang.id:04d}')

