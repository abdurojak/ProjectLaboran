from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.peminjaman.models import PeminjamanAlat
from apps.pengguna.models import Pengguna
from .models import Barang, InventarisBarang, Lokasi, PaketBarang


class LokasiModelTests(TestCase):
    def test_kode_lokasi_dibuat_dari_id_database(self):
        lokasi = Lokasi.objects.create(nama_lokasi='Lab Kimia')

        self.assertEqual(lokasi.kode_lokasi, f'LKS-{lokasi.id:04d}')
        self.assertEqual(len(lokasi.kode_lokasi), 8)


class LokasiViewTests(TestCase):
    def test_tambah_lokasi_tidak_meminta_kode_lokasi(self):
        response = self.client.get(reverse('inventaris:lokasi_create'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="kode_lokasi"')

    def test_daftar_lokasi_memakai_desain_dan_modal_konfirmasi_inventaris(self):
        lokasi = Lokasi.objects.create(nama_lokasi='Lab Kimia')

        response = self.client.get(reverse('inventaris:lokasi_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-confirmation-modal')
        self.assertContains(response, 'data-confirm-message="Yakin ingin menghapus lokasi Lab Kimia?"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, reverse('inventaris:lokasi_delete', args=[lokasi.pk]))


class BarangLokasiTests(TestCase):
    def test_form_create_inventaris_meminta_lokasi_untuk_detail_awal(self):
        lokasi = Lokasi.objects.create(nama_lokasi='Lab Fisika')

        response = self.client.get(reverse('inventaris:barang_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="lokasi"')
        self.assertContains(response, lokasi.nama_lokasi)

    def test_daftar_barang_menampilkan_nama_lokasi_dari_relasi(self):
        lokasi = Lokasi.objects.create(nama_lokasi='Ruang Alat')
        inventaris = InventarisBarang.objects.create(
            nama='Mikroskop',
            jumlah=2,
        )
        barang = Barang.objects.create(
            inventaris=inventaris,
            nama='Mikroskop',
            kode_barang='BRG001',
            jumlah=2,
            lokasi=lokasi,
        )

        response = self.client.get(reverse('inventaris:inventaris_detail', args=[inventaris.pk]))

        self.assertContains(response, barang.kode_barang)
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

        self.assertEqual(barang.kode_barang, 'BRG-0001')

    def test_kode_barang_berbeda_dari_kode_inventaris(self):
        lokasi = Lokasi.objects.create(nama_lokasi='Lab Pemrograman')
        inventaris = InventarisBarang.objects.create(nama='Keyboard', jumlah=2)
        barang = Barang.objects.create(
            inventaris=inventaris,
            nama='Keyboard',
            jumlah=2,
            lokasi=lokasi,
            kondisi='baik',
        )
        barang_lain = Barang.objects.create(
            inventaris=inventaris,
            nama='Keyboard',
            jumlah=2,
            lokasi=lokasi,
            kondisi='baik',
        )

        self.assertEqual(inventaris.kode_inventaris, 'LAB-0001')
        self.assertEqual(barang.kode_barang, 'BRG-0001')
        self.assertEqual(barang_lain.kode_barang, 'BRG-0002')


class BarangFotoFormTests(TestCase):
    def setUp(self):
        self.lokasi = Lokasi.objects.create(nama_lokasi='Lab Foto')
        self.barang = Barang.objects.create(
            nama='Kamera',
            jumlah=1,
            lokasi=self.lokasi,
            kondisi='baik',
            foto=SimpleUploadedFile('kamera.jpg', b'fake-image-content', content_type='image/jpeg'),
        )

    def test_form_edit_tidak_menampilkan_checkbox_hapus_bawaan(self):
        response = self.client.get(reverse('inventaris:barang_update', args=[self.barang.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'foto-clear_id')
        self.assertContains(response, 'data-delete-button')
        self.assertContains(response, 'data-file-upload')

    def test_tombol_hapus_preview_menghapus_foto_saat_disimpan(self):
        response = self.client.post(
            reverse('inventaris:barang_update', args=[self.barang.pk]),
            {
                'nama': 'Kamera',
                'jumlah': 1,
                'lokasi': self.lokasi.pk,
                'kondisi': 'baik',
                'hapus_foto': '1',
                'keterangan': '',
            },
        )

        self.assertRedirects(response, reverse('inventaris:barang_list'))
        self.barang.refresh_from_db()
        self.assertFalse(self.barang.foto)


class BarangListViewTests(TestCase):
    def setUp(self):
        self.pengguna = Pengguna.objects.create(
            nama_pengguna='Lab Admin',
            nim_nik='ADM-BARANG',
            email='admin-barang@example.com',
            password='rahasia123',
            no_hp='080000000002',
            alamat='Kampus',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()
        self.lab_pemrograman = Lokasi.objects.create(nama_lokasi='Lab Pemrograman')
        self.lab_ski = Lokasi.objects.create(nama_lokasi='Lab Sistem Keamanan Informasi')
        self.gudang = Lokasi.objects.create(nama_lokasi='Gudang')
        self.keyboard_inventaris = InventarisBarang.objects.create(
            nama='Keyboard',
            jumlah=5,
        )
        self.router_inventaris = InventarisBarang.objects.create(
            nama='Router',
            jumlah=2,
        )
        self.keyboard_barang = Barang.objects.create(
            inventaris=self.keyboard_inventaris,
            nama='Keyboard',
            jumlah=5,
            lokasi=self.lab_pemrograman,
            kondisi='baik',
        )
        self.keyboard_cadangan = Barang.objects.create(
            inventaris=self.keyboard_inventaris,
            nama='Keyboard',
            jumlah=5,
            lokasi=self.gudang,
            kondisi='rusak_ringan',
            keterangan='Cadangan',
        )
        Barang.objects.create(
            inventaris=self.router_inventaris,
            nama='Router',
            jumlah=2,
            lokasi=self.lab_ski,
            kondisi='rusak_ringan',
        )

    def test_search_filters_barang(self):
        response = self.client.get(reverse('inventaris:barang_list'), {'q': 'Router'})

        self.assertContains(response, 'Router')
        self.assertNotContains(response, 'Keyboard')

    def test_daftar_barang_hanya_menampilkan_pencarian(self):
        response = self.client.get(reverse('inventaris:barang_list'))

        self.assertContains(response, 'name="q"')
        self.assertNotContains(response, 'name="kondisi"')
        self.assertNotContains(response, 'name="lokasi"')

    def test_daftar_barang_memiliki_tombol_kelola_lokasi(self):
        response = self.client.get(reverse('inventaris:barang_list'))

        self.assertContains(response, 'Kelola Lokasi')
        self.assertContains(response, reverse('inventaris:lokasi_list'))

    def test_daftar_barang_menyembunyikan_tombol_kelola_paket(self):
        response = self.client.get(reverse('inventaris:barang_list'))

        self.assertNotContains(response, 'Kelola Paket')
        self.assertNotContains(response, reverse('inventaris:paket_list'))

    def test_detail_inventaris_search_filters_detail_barang(self):
        response = self.client.get(
            reverse('inventaris:inventaris_detail', args=[self.keyboard_inventaris.pk]),
            {'q': 'Cadangan'},
        )

        self.assertContains(response, 'Cadangan')
        self.assertEqual(list(response.context['detail_barang_list']), [self.keyboard_cadangan])

    def test_detail_inventaris_kondisi_filter_filters_detail_barang(self):
        response = self.client.get(
            reverse('inventaris:inventaris_detail', args=[self.keyboard_inventaris.pk]),
            {'kondisi': 'baik'},
        )

        self.assertEqual(list(response.context['detail_barang_list']), [self.keyboard_barang])

    def test_detail_inventaris_lokasi_filter_filters_detail_barang(self):
        response = self.client.get(
            reverse('inventaris:inventaris_detail', args=[self.keyboard_inventaris.pk]),
            {'lokasi': self.gudang.id},
        )

        self.assertEqual(list(response.context['detail_barang_list']), [self.keyboard_cadangan])

    def test_daftar_barang_menampilkan_stok_operasional(self):
        PeminjamanAlat.objects.create(
            barang=self.keyboard_barang,
            nama_peminjam='Budi',
            tanggal_pinjam='2026-06-21',
            tanggal_kembali='2026-06-22',
            status='dipinjam',
        )

        response = self.client.get(reverse('inventaris:barang_list'))

        self.assertContains(response, 'Stok Total')
        self.assertContains(response, 'Dipinjam')
        self.assertContains(response, 'Tersedia')
        self.assertContains(response, '3')

    def test_daftar_barang_mengarahkan_hapus_ke_komponen_konfirmasi(self):
        response = self.client.get(reverse('inventaris:barang_list'))

        self.assertContains(response, 'data-confirm-message="Yakin ingin menghapus barang Keyboard?"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, reverse('inventaris:barang_delete', args=[self.keyboard_inventaris.pk]))

    def test_detail_inventaris_menampilkan_list_detail_barang(self):
        response = self.client.get(reverse('inventaris:inventaris_detail', args=[self.keyboard_inventaris.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Barang')
        self.assertContains(response, self.keyboard_inventaris.kode_inventaris)
        self.assertContains(response, self.keyboard_barang.kode_barang)
        self.assertContains(response, 'Lab Pemrograman')
        self.assertContains(response, 'Status Pinjam')

    def test_detail_inventaris_mengarahkan_hapus_detail_ke_komponen_konfirmasi(self):
        response = self.client.get(reverse('inventaris:inventaris_detail', args=[self.keyboard_inventaris.pk]))

        self.assertContains(response, 'data-confirm-message="Yakin ingin menghapus detail barang')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, reverse('inventaris:detail_barang_delete', args=[self.keyboard_barang.pk]))


class DetailBarangCrudTests(TestCase):
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
        self.inventaris = InventarisBarang.objects.create(nama='Mikroskop', jumlah=3)
        self.lokasi_awal = Lokasi.objects.create(nama_lokasi='Ruang Alat')
        self.lokasi_baru = Lokasi.objects.create(nama_lokasi='Lab Biologi')
        self.barang = Barang.objects.create(
            inventaris=self.inventaris,
            nama='Mikroskop',
            jumlah=3,
            lokasi=self.lokasi_awal,
            kondisi='baik',
        )

    def test_detail_inventaris_memiliki_tombol_tambah_detail_barang(self):
        response = self.client.get(reverse('inventaris:inventaris_detail', args=[self.inventaris.pk]))

        self.assertContains(response, reverse('inventaris:detail_barang_create', args=[self.inventaris.pk]))
        self.assertContains(response, 'Tambah Detail Barang')

    def test_create_detail_barang_mengikat_ke_inventaris_parent(self):
        response = self.client.post(
            reverse('inventaris:detail_barang_create', args=[self.inventaris.pk]),
            {
                'lokasi': self.lokasi_baru.pk,
                'kondisi': 'rusak_ringan',
                'keterangan': 'Unit cadangan',
            },
        )

        detail = Barang.objects.exclude(pk=self.barang.pk).get()
        self.inventaris.refresh_from_db()
        self.assertRedirects(response, reverse('inventaris:inventaris_detail', args=[self.inventaris.pk]))
        self.assertEqual(detail.inventaris, self.inventaris)
        self.assertEqual(detail.nama, self.inventaris.nama)
        self.assertEqual(self.inventaris.jumlah, self.inventaris.detail_barang.count())
        self.assertEqual(detail.lokasi, self.lokasi_baru)
        self.assertEqual(detail.kondisi, 'rusak_ringan')

    def test_update_detail_barang_mengubah_lokasi_dan_kondisi(self):
        response = self.client.post(
            reverse('inventaris:detail_barang_update', args=[self.barang.pk]),
            {
                'lokasi': self.lokasi_baru.pk,
                'kondisi': 'rusak_ringan',
                'keterangan': 'Perlu dicek',
            },
        )
        self.barang.refresh_from_db()

        self.assertRedirects(response, reverse('inventaris:inventaris_detail', args=[self.inventaris.pk]))
        self.assertEqual(self.barang.lokasi, self.lokasi_baru)
        self.assertEqual(self.barang.kondisi, 'rusak_ringan')
        self.assertEqual(self.barang.keterangan, 'Perlu dicek')

    def test_delete_detail_barang_menghapus_child_saja(self):
        Barang.objects.create(
            inventaris=self.inventaris,
            nama='Mikroskop',
            jumlah=3,
            lokasi=self.lokasi_baru,
            kondisi='baik',
        )
        self.inventaris.sync_jumlah_from_detail()
        self.assertEqual(self.inventaris.jumlah, 2)

        response = self.client.post(reverse('inventaris:detail_barang_delete', args=[self.barang.pk]))
        self.inventaris.refresh_from_db()

        self.assertRedirects(response, reverse('inventaris:inventaris_detail', args=[self.inventaris.pk]))
        self.assertFalse(Barang.objects.filter(pk=self.barang.pk).exists())
        self.assertTrue(InventarisBarang.objects.filter(pk=self.inventaris.pk).exists())
        self.assertEqual(self.inventaris.jumlah, 1)

    def test_detail_barang_menampilkan_status_pinjam_tersedia(self):
        response = self.client.get(reverse('inventaris:barang_detail', args=[self.barang.pk]))

        self.assertContains(response, 'Status Pinjam')
        self.assertContains(response, 'Tersedia')

    def test_detail_barang_menampilkan_status_pinjam_dipinjam(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            tanggal_pinjam='2026-06-21',
            tanggal_kembali='2026-06-22',
            status='dipinjam',
        )

        detail_response = self.client.get(reverse('inventaris:barang_detail', args=[self.barang.pk]))
        list_response = self.client.get(reverse('inventaris:inventaris_detail', args=[self.inventaris.pk]))

        self.assertContains(detail_response, 'Dipinjam')
        self.assertContains(list_response, 'Dipinjam')


class InventarisCrudTests(TestCase):
    def setUp(self):
        self.lokasi = Lokasi.objects.create(nama_lokasi='Gudang Utama')

    def test_create_inventaris_otomatis_membuat_detail_sejumlah_stok(self):
        response = self.client.post(
            reverse('inventaris:barang_create'),
            {
                'nama': 'Osiloskop',
                'jumlah': 3,
                'lokasi': self.lokasi.pk,
                'keterangan': 'Unit praktikum',
            },
        )
        inventaris = InventarisBarang.objects.get(nama='Osiloskop')

        self.assertRedirects(response, reverse('inventaris:barang_list'))
        self.assertEqual(inventaris.detail_barang.count(), 3)
        self.assertTrue(inventaris.detail_barang.filter(kondisi='baik', lokasi=self.lokasi).count(), 3)

    def test_edit_inventaris_tidak_meminta_lokasi_atau_stok(self):
        inventaris = InventarisBarang.objects.create(nama='Osiloskop', jumlah=3)

        response = self.client.get(reverse('inventaris:barang_update', args=[inventaris.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="jumlah"')
        self.assertNotContains(response, 'name="lokasi"')

    def test_delete_inventaris_menghapus_semua_detail_barang(self):
        inventaris = InventarisBarang.objects.create(nama='Osiloskop', jumlah=2)
        Barang.objects.create(inventaris=inventaris, nama='Osiloskop', jumlah=2, lokasi=self.lokasi)
        Barang.objects.create(inventaris=inventaris, nama='Osiloskop', jumlah=2, lokasi=self.lokasi)

        response = self.client.post(reverse('inventaris:barang_delete', args=[inventaris.pk]))

        self.assertRedirects(response, reverse('inventaris:barang_list'))
        self.assertFalse(InventarisBarang.objects.filter(pk=inventaris.pk).exists())
        self.assertFalse(Barang.objects.filter(inventaris_id=inventaris.pk).exists())

    def test_delete_inventaris_memakai_komponen_konfirmasi(self):
        inventaris = InventarisBarang.objects.create(nama='Osiloskop', jumlah=2)

        response = self.client.get(reverse('inventaris:barang_delete', args=[inventaris.pk]))

        self.assertRedirects(response, reverse('inventaris:barang_list'), fetch_redirect_response=False)


class PaketBarangTests(TestCase):
    def setUp(self):
        self.pengguna = Pengguna.objects.create(
            nama_pengguna='Lab Admin',
            nim_nik='ADM-PAKET',
            email='admin-paket@example.com',
            password='rahasia123',
            no_hp='080000000001',
            alamat='Kampus',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()
        self.keyboard = InventarisBarang.objects.create(nama='Keyboard', jumlah=3)
        self.mouse = InventarisBarang.objects.create(nama='Mouse', jumlah=2)

    def test_kode_paket_dibuat_otomatis(self):
        paket = PaketBarang.objects.create(nama='Paket Lab Dasar')

        self.assertEqual(paket.kode_paket, f'PKT-{paket.id:04d}')

    def test_crud_paket_menyimpan_item_barang_dan_jumlah(self):
        response = self.client.post(reverse('inventaris:paket_create'), {
            'nama': 'Paket Lab Dasar',
            'keterangan': 'Untuk praktikum dasar',
            'aktif': 'on',
            'items-TOTAL_FORMS': '2',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-inventaris': self.keyboard.pk,
            'items-0-jumlah': '2',
            'items-1-inventaris': self.mouse.pk,
            'items-1-jumlah': '1',
        })

        paket = PaketBarang.objects.get(nama='Paket Lab Dasar')
        self.assertRedirects(response, reverse('inventaris:paket_detail', args=[paket.pk]))
        self.assertEqual(paket.items.count(), 2)
        self.assertTrue(paket.items.filter(inventaris=self.keyboard, jumlah=2).exists())
        self.assertTrue(paket.items.filter(inventaris=self.mouse, jumlah=1).exists())

    def test_daftar_paket_memakai_desain_dan_konfirmasi(self):
        paket = PaketBarang.objects.create(nama='Paket Kamera')

        response = self.client.get(reverse('inventaris:paket_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Daftar Paket')
        self.assertContains(response, reverse('inventaris:paket_create'))
        self.assertContains(response, 'data-confirmation-modal')
        self.assertContains(response, f'Yakin ingin menghapus paket {paket.nama}?')
