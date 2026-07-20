from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.pengguna.models import Pengguna
from apps.kalender.models import Notifikasi

from .models import BarangTertinggal


class BarangTertinggalViewTests(TestCase):
    def setUp(self):
        self.laboran = Pengguna.objects.create(
            nama_pengguna='Laboran Barang Tertinggal',
            nim_nik='LAB-BRT',
            email='laboran-brt@trisakti.ac.id',
            password='rahasia123',
            no_hp='080000000003',
            alamat='Kampus',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        session = self.client.session
        session['pengguna_id'] = self.laboran.pk
        session.save()
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
        self.assertContains(response, 'Hilang')
        self.assertContains(response, 'Diambil')
        self.assertNotContains(response, 'Diajukan')
        self.assertNotContains(response, 'Rusak')
        self.assertContains(response, 'data-confirmation-modal')
        self.assertContains(response, reverse('barang_tertinggal:delete', args=[self.barang.pk]))

    def test_form_hanya_memiliki_tiga_status_barang_tertinggal(self):
        response = self.client.get(reverse('barang_tertinggal:create'))

        self.assertContains(response, '<option value="tertinggal"', html=False)
        self.assertContains(response, '<option value="hilang"', html=False)
        self.assertContains(response, '<option value="diambil"', html=False)
        self.assertNotContains(response, '<option value="diajukan"', html=False)
        self.assertNotContains(response, '<option value="rusak"', html=False)

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
                'lokasi_ditemukan': 'Lab Pemrograman meja 4',
                'tanggal_diambil': '',
                'nama_pemilik': '',
                'nim_pemilik': '',
                'status': 'tertinggal',
                'foto': foto,
            },
        )

        barang = BarangTertinggal.objects.get(nama_barang='Botol Minum')
        self.assertRedirects(response, reverse('barang_tertinggal:list'))
        self.assertEqual(barang.kode_barang_tertinggal, f'BRT-260623-{barang.id:04d}')
        self.assertTrue(barang.foto)
        self.assertEqual(barang.lokasi_ditemukan, 'Lab Pemrograman meja 4')

    def test_create_menerbitkan_berita_dan_notifikasi_mahasiswa(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Penerima Berita', nim_nik='06400239991',
            email='berita@std.trisakti.ac.id', password='rahasia123', no_hp='081299991',
            alamat='Jakarta', fakultas='Teknologi Industri', prodi='Informatika',
            gender='laki_laki', role='mahasiswa',
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('barang_tertinggal:create'), {
                'nama_barang': 'Kalkulator Biru',
                'jenis_barang': 'Elektronik',
                'jumlah_barang': 1,
                'lokasi_ditemukan': 'Lab Rekayasa Data',
                'tanggal_ditemukan': '2026-07-20',
                'tanggal_diambil': '',
                'nama_pemilik': '',
                'nim_pemilik': '',
                'status': 'tertinggal',
            })

        barang = BarangTertinggal.objects.get(nama_barang='Kalkulator Biru')
        self.assertRedirects(response, reverse('barang_tertinggal:list'))
        notification = Notifikasi.objects.get(
            pengguna=mahasiswa,
            source_key=f'barang-tertinggal:{barang.pk}:published',
        )
        self.assertIn('Kalkulator Biru', notification.judul)
        self.assertEqual(notification.url, reverse('barang_tertinggal:berita_detail', args=[barang.pk]))

    def test_mahasiswa_melihat_berita_aktif_dan_bukan_barang_diambil(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Berita', nim_nik='06400239992',
            email='berita2@std.trisakti.ac.id', password='rahasia123', no_hp='081299992',
            alamat='Jakarta', fakultas='Teknologi Industri', prodi='Informatika',
            gender='perempuan', role='mahasiswa',
        )
        sudah_diambil = BarangTertinggal.objects.create(
            nama_barang='Barang Selesai', jenis_barang='Lainnya', jumlah_barang=1,
            lokasi_ditemukan='Laboratorium', tanggal_ditemukan='2026-07-19', status='diambil',
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('barang_tertinggal:berita_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Flashdisk')
        self.assertNotContains(response, sudah_diambil.nama_barang)
        detail = self.client.get(reverse('barang_tertinggal:berita_detail', args=[self.barang.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self.barang.kode_barang_tertinggal)

        dashboard = self.client.get(reverse('dashboard:home'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, 'Berita Barang Hilang')
        self.assertContains(dashboard, self.barang.nama_barang)

    def test_laboran_tidak_dapat_membuka_hal_berita_mahasiswa(self):
        response = self.client.get(reverse('barang_tertinggal:berita_list'))
        self.assertRedirects(response, reverse('dashboard:home'))

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
                'nim_pemilik': '06400230001',
                'status': 'diambil',
            },
        )

        self.barang.refresh_from_db()
        self.assertRedirects(response, reverse('barang_tertinggal:list'))
        self.assertEqual(self.barang.nama_barang, 'Flashdisk Sandisk')
        self.assertEqual(self.barang.status, 'diambil')
        self.assertEqual(self.barang.nim_pemilik, '06400230001')

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
                'nim_pemilik': '',
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

    def test_barang_tertinggal_terhubung_ke_akun_jika_nim_cocok(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Pemilik',
            nim_nik='06400230099',
            email='pemilik@example.com',
            password='rahasia123',
            no_hp='080000000009',
            alamat='Kampus',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )

        barang = BarangTertinggal.objects.create(
            nama_barang='Kartu Mahasiswa',
            jenis_barang='Kartu',
            jumlah_barang=1,
            tanggal_ditemukan='2026-06-22',
            nim_pemilik='06400230099',
        )

        self.assertEqual(barang.pemilik, pengguna)

    def test_barang_tertinggal_lama_bisa_dihubungkan_saat_akun_ada(self):
        barang = BarangTertinggal.objects.create(
            nama_barang='Dompet',
            jenis_barang='Pribadi',
            jumlah_barang=1,
            tanggal_ditemukan='2026-06-22',
            nim_pemilik='06400230100',
        )
        pengguna = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Baru',
            nim_nik='06400230100',
            email='baru@example.com',
            password='rahasia123',
            no_hp='080000000010',
            alamat='Kampus',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )

        from .services import link_barang_tertinggal_to_pengguna
        link_barang_tertinggal_to_pengguna(pengguna)

        barang.refresh_from_db()
        self.assertEqual(barang.pemilik, pengguna)

