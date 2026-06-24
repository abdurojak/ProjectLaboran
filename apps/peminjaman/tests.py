from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.inventaris.models import Barang, Lokasi
from apps.pengguna.models import Pengguna
from .models import PeminjamanAlat


class PeminjamanViewsTests(TestCase):
    def setUp(self):
        self.pengguna = Pengguna.objects.create(
            nama_pengguna='Lab Admin',
            nim_nik='ADM001',
            email='admin@example.com',
            password='rahasia123',
            no_hp='080000000000',
            alamat='Kampus',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()
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
        self.assertContains(response, 'data-confirm-message="Yakin ingin menghapus peminjaman Andi Pratama?"')
        self.assertContains(response, 'method="post"')
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
        self.assertContains(response, 'data-confirm-message="Yakin ingin menghapus peminjaman Andi Pratama?"')
        self.assertContains(response, 'method="post"')

    def test_create_menolak_detail_barang_rusak_berat(self):
        response = self.client.post(
            reverse('peminjaman:peminjaman_create'),
            {
                'selected_barang_ids': str(self.barang_rusak_berat.pk),
                'nama_peminjam': 'Budi',
                'nim': '2201002',
                'no_hp': '081111111111',
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

    def test_create_menolak_detail_barang_yang_sedang_dipinjam(self):
        response = self.client.post(
            reverse('peminjaman:peminjaman_create'),
            {
                'selected_barang_ids': str(self.barang.pk),
                'nama_peminjam': 'Budi',
                'nim': '2201002',
                'no_hp': '081111111111',
                'tanggal_pinjam': '2026-06-21',
                'tanggal_kembali': '2026-06-22',
                'status': 'diajukan',
                'catatan': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pilih minimal satu detail barang yang tersedia dan tidak rusak berat.')
        self.assertFalse(PeminjamanAlat.objects.filter(nama_peminjam='Budi').exists())

    def test_filter_peminjaman_berdasarkan_nama_barang_range_tanggal_status_dan_peminjaman_saya(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Siti Aminah',
            nim_nik='2201002',
            email='siti@example.com',
            password='rahasia123',
            no_hp='081111111111',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        PeminjamanAlat.objects.create(
            barang=self.barang_lain,
            nama_peminjam='Siti Aminah',
            nim='2201002',
            no_hp='081111111111',
            tanggal_pinjam=date(2026, 6, 23),
            tanggal_kembali=date(2026, 6, 24),
            status='diajukan',
        )
        PeminjamanAlat.objects.create(
            barang=self.barang_tersedia_lain,
            nama_peminjam='Budi',
            nim='2201003',
            no_hp='081222222222',
            tanggal_pinjam=date(2026, 7, 1),
            tanggal_kembali=date(2026, 7, 2),
            status='dikembalikan',
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(
            reverse('peminjaman:peminjaman_list'),
            {
                'barang': 'Mikroskop',
                'tanggal_mulai': '2026-06-20',
                'tanggal_selesai': '2026-06-30',
                'status': 'diajukan',
                'milik_saya': '1',
            },
        )

        self.assertContains(response, 'Siti Aminah')
        self.assertNotContains(response, 'Budi')
        self.assertContains(response, 'name="milik_saya"')

    def test_filter_peminjaman_saya_tidak_muncul_untuk_laboran(self):
        response = self.client.get(reverse('peminjaman:peminjaman_list'))

        self.assertNotContains(response, 'name="milik_saya"')


class PeminjamanMahasiswaTests(TestCase):
    def setUp(self):
        self.mahasiswa = Pengguna.objects.create(
            nama_pengguna='Siti Aminah',
            nim_nik='2201002',
            email='siti@example.com',
            password='rahasia123',
            no_hp='081111111111',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        session = self.client.session
        session['pengguna_id'] = self.mahasiswa.pk
        session.save()
        self.lokasi = Lokasi.objects.create(nama_lokasi='Gudang A')
        self.barang = Barang.objects.create(
            nama='Kamera',
            kode_barang='LAB-010',
            jumlah=1,
            lokasi=self.lokasi,
            kondisi='baik',
        )

    def test_mahasiswa_create_peminjaman_otomatis_diajukan(self):
        response = self.client.post(
            reverse('peminjaman:peminjaman_create'),
            {
                'selected_barang_ids': str(self.barang.pk),
                'nama_peminjam': 'Siti Aminah',
                'nim': '2201002',
                'no_hp': '081111111111',
                'tanggal_pinjam': '2026-06-21',
                'tanggal_kembali': '2026-06-22',
                'status': 'dipinjam',
                'catatan': '',
            },
        )

        peminjaman = PeminjamanAlat.objects.get(barang=self.barang)
        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        self.assertEqual(peminjaman.status, 'diajukan')
        self.assertEqual(peminjaman.nim, self.mahasiswa.nim_nik)
        self.assertEqual(peminjaman.nama_peminjam, self.mahasiswa.nama_pengguna)
        self.assertEqual(peminjaman.no_hp, self.mahasiswa.no_hp)

    def test_form_mahasiswa_tidak_menampilkan_input_identitas(self):
        response = self.client.get(reverse('peminjaman:peminjaman_create'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'type="text" name="nama_peminjam"')
        self.assertNotContains(response, 'type="text" name="nim"')
        self.assertNotContains(response, 'type="text" name="no_hp"')

    def test_mahasiswa_bisa_edit_atau_hapus_peminjaman_miliknya_yang_masih_diajukan(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti Aminah',
            nim='2201002',
            no_hp='081111111111',
            tanggal_pinjam=date(2026, 6, 21),
            tanggal_kembali=date(2026, 6, 22),
            status='diajukan',
        )

        update_response = self.client.get(reverse('peminjaman:peminjaman_update', args=[peminjaman.pk]))

        self.assertEqual(update_response.status_code, 200)

    def test_mahasiswa_tidak_bisa_edit_atau_hapus_peminjaman_yang_bukan_diajukan(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti Aminah',
            nim='2201002',
            no_hp='081111111111',
            tanggal_pinjam=date(2026, 6, 21),
            tanggal_kembali=date(2026, 6, 22),
            status='dipinjam',
        )

        update_response = self.client.get(reverse('peminjaman:peminjaman_update', args=[peminjaman.pk]))
        delete_response = self.client.post(reverse('peminjaman:peminjaman_delete', args=[peminjaman.pk]))

        self.assertRedirects(update_response, reverse('peminjaman:peminjaman_list'))
        self.assertRedirects(delete_response, reverse('peminjaman:peminjaman_list'))
        self.assertTrue(PeminjamanAlat.objects.filter(pk=peminjaman.pk).exists())

    def test_mahasiswa_tidak_bisa_edit_peminjaman_orang_lain(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            nim='2201003',
            no_hp='081222222222',
            tanggal_pinjam=date(2026, 6, 21),
            tanggal_kembali=date(2026, 6, 22),
            status='diajukan',
        )

        response = self.client.get(reverse('peminjaman:peminjaman_update', args=[peminjaman.pk]))

        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))


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
            tanggal_pinjam=date(2026, 6, 22),
            tanggal_kembali=date(2026, 6, 23),
        )

        self.assertEqual(peminjaman.kode_pinjam, f'PJM-260622-{peminjaman.id:04d}')
