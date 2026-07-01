from datetime import date

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.inventaris.models import Barang, InventarisBarang, Lokasi, PaketBarang, PaketBarangItem
from apps.pengguna.models import Pengguna
from .models import PeminjamanAlat, PeminjamanTransaksi


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

    def test_list_page_membatasi_scroll_horizontal_di_card_tabel(self):
        response = self.client.get(reverse('peminjaman:peminjaman_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'min-w-0 max-w-full space-y-6 overflow-x-hidden')
        self.assertContains(response, 'max-w-full overflow-x-auto overscroll-x-contain')
        self.assertContains(response, 'w-full min-w-[920px]')

    def test_filter_peminjaman_otomatis_responsif_tanpa_tombol_filter(self):
        response = self.client.get(reverse('peminjaman:peminjaman_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-auto-filter-form')
        self.assertContains(response, 'grid min-w-0 gap-4 md:grid-cols-2 lg:grid-cols-4')
        self.assertContains(response, 'Semua status')
        self.assertContains(response, 'submitFilter()')
        self.assertNotContains(response, '<span>Filter</span>')

    def test_list_page_memakai_modal_konfirmasi_hapus(self):
        self.peminjaman.status = 'diajukan'
        self.peminjaman.save(update_fields=['status'])
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
        self.peminjaman.status = 'diajukan'
        self.peminjaman.save(update_fields=['status'])
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
        self.assertContains(response, 'name="selected_barang_ids"')
        self.assertContains(response, 'data-barang-picker-done')
        self.assertContains(response, '<th>Jumlah</th>')
        self.assertContains(response, 'data-barang-quantity')
        self.assertContains(response, reverse('peminjaman:barang_options'))
        self.assertContains(response, 'data-barang-picker-body')
        self.assertContains(response, 'data-barang-page-next')
        self.assertContains(response, '<th>Foto</th>')
        self.assertContains(response, 'data-barang-photo-modal')
        self.assertContains(response, 'data-barang-photo-heading')
        self.assertContains(response, 'Foto barang belum tersedia.')
        self.assertContains(response, "input.inputMode = 'numeric'")
        self.assertContains(response, 'availableItems.some')
        self.assertContains(response, 'clearGroupSelection(group)')
        self.assertContains(response, 'commitQuantityInput(input)')
        self.assertNotContains(response, "pickerBody.addEventListener('input'")
        self.assertContains(response, 'modalSelectionSnapshot')
        self.assertContains(response, 'restoreModalSelectionSnapshot()')
        self.assertContains(response, "closeModal({restore: true})")
        self.assertContains(response, "closeModal({restore: false})")
        self.assertContains(response, 'document.body.appendChild(dialog)')
        self.assertNotContains(response, '<select name="barang"')
        self.assertNotContains(response, 'id="id_barang_display"')
        self.assertNotContains(response, 'badge.innerHTML')

    def test_filter_tanggal_invalid_tidak_menyebabkan_server_error(self):
        response = self.client.get(
            reverse('peminjaman:peminjaman_list'),
            {'tanggal_mulai': 'bukan-tanggal', 'tanggal_selesai': 'juga-bukan-tanggal'},
        )

        self.assertEqual(response.status_code, 200)

    def test_list_peminjaman_memakai_pagination(self):
        for index in range(30):
            PeminjamanAlat.objects.create(
                barang=self.barang_lain,
                nama_peminjam=f'Peminjam {index}',
                tanggal_pinjam=date(2026, 7, 1),
                tanggal_kembali=date(2026, 7, 2),
                status='dipinjam',
            )

        response = self.client.get(reverse('peminjaman:peminjaman_list'))

        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(len(response.context['peminjaman_list']), 10)
        self.assertContains(response, 'Berikutnya')

    def test_list_default_menyembunyikan_status_arsip_dan_semua_menampilkannya(self):
        PeminjamanAlat.objects.create(
            barang=self.barang_lain,
            nama_peminjam='Riwayat Ditolak',
            tanggal_pinjam=date(2026, 7, 1),
            tanggal_kembali=date(2026, 7, 2),
            status='ditolak',
        )
        PeminjamanAlat.objects.create(
            barang=self.barang_tersedia_lain,
            nama_peminjam='Riwayat Digantikan',
            tanggal_pinjam=date(2026, 7, 1),
            tanggal_kembali=date(2026, 7, 2),
            status='digantikan',
        )
        PeminjamanAlat.objects.create(
            barang=self.barang_rusak,
            nama_peminjam='Riwayat Dikembalikan',
            tanggal_pinjam=date(2026, 7, 1),
            tanggal_kembali=date(2026, 7, 2),
            status='dikembalikan',
        )

        default_response = self.client.get(reverse('peminjaman:peminjaman_list'))
        semua_response = self.client.get(reverse('peminjaman:peminjaman_list'), {'semua': '1'})

        self.assertNotContains(default_response, 'Riwayat Ditolak')
        self.assertNotContains(default_response, 'Riwayat Digantikan')
        self.assertNotContains(default_response, 'Riwayat Dikembalikan')
        self.assertContains(default_response, 'name="semua"')
        self.assertContains(semua_response, 'Riwayat Ditolak')
        self.assertContains(semua_response, 'Riwayat Digantikan')
        self.assertContains(semua_response, 'Riwayat Dikembalikan')
        self.assertContains(semua_response, 'id="id_semua_filter"')
        self.assertContains(semua_response, 'checked')

    def test_detail_page_menampilkan_foto_barang(self):
        response = self.client.get(reverse('peminjaman:peminjaman_detail', args=[self.peminjaman.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Foto Barang')
        self.assertContains(response, 'Foto barang belum tersedia.')

    def test_preview_dan_detail_memakai_foto_parent_inventaris(self):
        inventaris = InventarisBarang.objects.create(
            nama='Kamera Induk',
            jumlah=1,
            foto='barang/kamera-parent.jpg',
        )
        barang = Barang.objects.create(
            inventaris=inventaris,
            nama='Kamera Induk',
            kode_barang='LAB-099',
            jumlah=1,
            lokasi=self.lokasi,
            kondisi='baik',
        )
        peminjaman = PeminjamanAlat.objects.create(
            barang=barang,
            nama_peminjam='Ari',
            tanggal_pinjam=date(2026, 6, 21),
            tanggal_kembali=date(2026, 6, 22),
        )

        options_response = self.client.get(reverse('peminjaman:barang_options'), {'q': 'LAB-099'})
        detail_response = self.client.get(reverse('peminjaman:peminjaman_detail', args=[peminjaman.pk]))

        self.assertEqual(options_response.json()['results'][0]['photo_url'], '/media/barang/kamera-parent.jpg')
        self.assertContains(detail_response, '/media/barang/kamera-parent.jpg')

    def test_form_edit_menampilkan_detail_barang_terpilih_sebagai_badge(self):
        response = self.client.get(reverse('peminjaman:peminjaman_update', args=[self.peminjaman.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-selected-barang-id="{self.barang.pk}"')
        self.assertContains(response, f'{self.barang.kode_barang} - {self.barang.nama}')
        self.assertContains(response, 'data-selected-barang-remove')

    def test_form_edit_tidak_bisa_dipakai_untuk_mengubah_status(self):
        response = self.client.post(
            reverse('peminjaman:peminjaman_update', args=[self.peminjaman.pk]),
            {
                'barang': str(self.barang.pk),
                'nama_peminjam': self.peminjaman.nama_peminjam,
                'nim': self.peminjaman.nim,
                'no_hp': self.peminjaman.no_hp,
                'tanggal_pinjam': '2026-06-18',
                'tanggal_kembali': '2026-06-20',
                'status': 'dikembalikan',
                'catatan': 'Catatan diperbarui',
            },
        )
        self.peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        self.assertEqual(self.peminjaman.status, 'dipinjam')
        self.assertEqual(self.peminjaman.catatan, 'Catatan diperbarui')

    def test_barang_dipinjam_dan_rusak_berat_tidak_bisa_dipilih(self):
        response = self.client.get(reverse('peminjaman:barang_options'))
        results = {item['kode']: item for item in response.json()['results']}

        self.assertEqual(len(results), 1)
        self.assertFalse(results[self.barang.kode_barang]['disabled'])
        self.assertEqual(results[self.barang.kode_barang]['group_available_count'], 3)
        self.assertNotIn(
            f'{self.barang_rusak_berat.kode_barang} - {self.barang_rusak_berat.nama}',
            [item['label'] for item in results[self.barang.kode_barang]['group_available_items']],
        )

    def test_endpoint_barang_options_mencari_dan_membatasi_20_item_per_halaman(self):
        for index in range(25):
            Barang.objects.create(
                nama=f'Kabel USB {index}',
                kode_barang=f'USB-{index:03d}',
                jumlah=1,
                lokasi=self.lokasi,
                kondisi='baik',
            )

        response = self.client.get(reverse('peminjaman:barang_options'), {'q': 'Kabel USB'})
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload['results']), 20)
        self.assertTrue(payload['has_next'])

    def test_endpoint_barang_options_mengelompokkan_per_nama_barang(self):
        Barang.objects.create(
            nama='Tripod Kamera',
            kode_barang='TRP-001',
            jumlah=1,
            lokasi=self.lokasi,
            kondisi='baik',
        )
        Barang.objects.create(
            nama='Tripod Kamera',
            kode_barang='TRP-002',
            jumlah=1,
            lokasi=self.lokasi,
            kondisi='baik',
        )

        response = self.client.get(reverse('peminjaman:barang_options'), {'q': 'Tripod Kamera'})
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload['results']), 1)
        self.assertEqual(payload['results'][0]['nama'], 'Tripod Kamera')
        self.assertEqual(payload['results'][0]['group_available_count'], 2)
        self.assertEqual(
            [item['label'] for item in payload['results'][0]['group_available_items']],
            ['TRP-001 - Tripod Kamera', 'TRP-002 - Tripod Kamera'],
        )

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
        self.assertContains(response, 'Menampilkan riwayat peminjaman Anda')

    def test_filter_peminjaman_saya_tidak_muncul_untuk_laboran(self):
        response = self.client.get(reverse('peminjaman:peminjaman_list'))

        self.assertNotContains(response, 'name="milik_saya"')


class PeminjamanMahasiswaTests(TestCase):
    def setUp(self):
        Pengguna.objects.create(
            nama_pengguna='Lab Admin',
            nim_nik='ADM-PJM',
            email='admin-peminjaman@example.com',
            password='rahasia123',
            no_hp='080000000000',
            alamat='Kampus',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
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
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Pengajuan Peminjaman Alat Baru', mail.outbox[0].subject)

    def test_mahasiswa_bisa_meminjam_paket_dan_membuat_peminjaman_per_item(self):
        inventaris_kamera = InventarisBarang.objects.create(nama='Kamera Paket', jumlah=2)
        inventaris_tripod = InventarisBarang.objects.create(nama='Tripod Paket', jumlah=1)
        kamera_1 = Barang.objects.create(inventaris=inventaris_kamera, nama='Kamera Paket', jumlah=2, lokasi=self.lokasi)
        kamera_2 = Barang.objects.create(inventaris=inventaris_kamera, nama='Kamera Paket', jumlah=2, lokasi=self.lokasi)
        tripod = Barang.objects.create(inventaris=inventaris_tripod, nama='Tripod Paket', jumlah=1, lokasi=self.lokasi)
        paket = PaketBarang.objects.create(nama='Paket Dokumentasi')
        PaketBarangItem.objects.create(paket=paket, inventaris=inventaris_kamera, jumlah=2)
        PaketBarangItem.objects.create(paket=paket, inventaris=inventaris_tripod, jumlah=1)

        response = self.client.post(
            reverse('peminjaman:peminjaman_create'),
            {
                'paket': str(paket.pk),
                'tanggal_pinjam': '2026-06-21',
                'tanggal_kembali': '2026-06-22',
                'status': 'dipinjam',
                'catatan': 'Pinjam paket',
            },
        )

        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        peminjaman_list = PeminjamanAlat.objects.filter(paket=paket)
        self.assertEqual(peminjaman_list.count(), 3)
        self.assertEqual({item.barang_id for item in peminjaman_list}, {kamera_1.pk, kamera_2.pk, tripod.pk})
        self.assertTrue(peminjaman_list.filter(status='diajukan').count(), 3)

    def test_satu_submit_multi_barang_memakai_satu_kode_pinjam(self):
        barang_kedua = Barang.objects.create(
            nama='Kamera Tambahan',
            kode_barang='CAM-TAMBAHAN',
            jumlah=1,
            lokasi=self.lokasi,
            kondisi='baik',
        )

        response = self.client.post(reverse('peminjaman:peminjaman_create'), {
            'selected_barang_ids': f'{self.barang.pk},{barang_kedua.pk}',
            'tanggal_pinjam': '2026-06-21',
            'tanggal_kembali': '2026-06-22',
            'catatan': 'Pinjam dua barang',
        })

        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        peminjaman_list = list(PeminjamanAlat.objects.filter(nim=self.mahasiswa.nim_nik).order_by('barang__kode_barang'))
        self.assertEqual(len(peminjaman_list), 2)
        self.assertEqual(len({peminjaman.kode_pinjam for peminjaman in peminjaman_list}), 1)
        self.assertEqual(len({peminjaman.transaksi_id for peminjaman in peminjaman_list}), 1)

        admin_session = self.client.session
        admin = Pengguna.objects.get(nim_nik='ADM-PJM')
        admin_session['pengguna_id'] = admin.pk
        admin_session.save()
        list_response = self.client.get(reverse('peminjaman:peminjaman_list'))

        self.assertContains(list_response, '2 barang')
        self.assertContains(list_response, 'Dalam transaksi ini')

    def test_admin_bulk_update_status_mengubah_semua_detail_transaksi(self):
        barang_kedua = Barang.objects.create(
            nama='Kamera Tambahan',
            kode_barang='CAM-BULK',
            jumlah=1,
            lokasi=self.lokasi,
            kondisi='baik',
        )
        response = self.client.post(reverse('peminjaman:peminjaman_create'), {
            'selected_barang_ids': f'{self.barang.pk},{barang_kedua.pk}',
            'tanggal_pinjam': '2026-06-21',
            'tanggal_kembali': '2026-06-22',
            'catatan': 'Bulk status',
        })
        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        transaksi_id = PeminjamanAlat.objects.filter(nim=self.mahasiswa.nim_nik).first().transaksi_id

        admin_session = self.client.session
        admin = Pengguna.objects.get(nim_nik='ADM-PJM')
        admin_session['pengguna_id'] = admin.pk
        admin_session.save()

        response = self.client.post(reverse('peminjaman:peminjaman_bulk_update'), {
            'transaksi_ids': [str(transaksi_id)],
            'status': 'dipinjam',
        })

        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        self.assertEqual(
            set(PeminjamanAlat.objects.filter(transaksi_id=transaksi_id).values_list('status', flat=True)),
            {'dipinjam'},
        )

    def test_admin_bisa_mengubah_status_detail_peminjaman_dengan_checkbox(self):
        barang_kedua = Barang.objects.create(
            nama='Kamera Tambahan',
            kode_barang='CAM-DETAIL',
            jumlah=1,
            lokasi=self.lokasi,
            kondisi='baik',
        )
        response = self.client.post(reverse('peminjaman:peminjaman_create'), {
            'selected_barang_ids': f'{self.barang.pk},{barang_kedua.pk}',
            'tanggal_pinjam': '2026-06-21',
            'tanggal_kembali': '2026-06-22',
            'catatan': 'Detail status',
        })
        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        peminjaman_satu, peminjaman_dua = PeminjamanAlat.objects.filter(
            nim=self.mahasiswa.nim_nik,
        ).order_by('barang__kode_barang')

        admin_session = self.client.session
        admin = Pengguna.objects.get(nim_nik='ADM-PJM')
        admin_session['pengguna_id'] = admin.pk
        admin_session.save()

        detail_response = self.client.get(reverse('peminjaman:peminjaman_detail', args=[peminjaman_satu.pk]))
        self.assertContains(detail_response, 'name="detail_ids"')
        self.assertContains(detail_response, 'name="status"')
        self.assertContains(detail_response, reverse('peminjaman:peminjaman_detail_status_update', args=[peminjaman_satu.pk]))
        self.assertNotContains(detail_response, '<option value="ditolak">Ditolak</option>', html=True)

        update_response = self.client.post(
            reverse('peminjaman:peminjaman_detail_status_update', args=[peminjaman_satu.pk]),
            {'detail_ids': [str(peminjaman_satu.pk)], 'status': 'dipinjam'},
        )
        peminjaman_satu.refresh_from_db()
        peminjaman_dua.refresh_from_db()

        self.assertRedirects(update_response, reverse('peminjaman:peminjaman_detail', args=[peminjaman_satu.pk]))
        self.assertEqual(peminjaman_satu.status, 'dipinjam')
        self.assertEqual(peminjaman_dua.status, 'diajukan')

    def test_admin_edit_peminjaman_memperbarui_transaksi_dan_semua_detail(self):
        barang_kedua = Barang.objects.create(
            nama='Kamera Tambahan',
            kode_barang='CAM-EDIT',
            jumlah=1,
            lokasi=self.lokasi,
            kondisi='baik',
        )
        response = self.client.post(reverse('peminjaman:peminjaman_create'), {
            'selected_barang_ids': f'{self.barang.pk},{barang_kedua.pk}',
            'tanggal_pinjam': '2026-06-21',
            'tanggal_kembali': '2026-06-22',
            'catatan': 'Sebelum edit',
        })
        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        peminjaman = PeminjamanAlat.objects.filter(nim=self.mahasiswa.nim_nik).first()
        transaksi_id = peminjaman.transaksi_id

        admin_session = self.client.session
        admin = Pengguna.objects.get(nim_nik='ADM-PJM')
        admin_session['pengguna_id'] = admin.pk
        admin_session.save()

        response = self.client.post(reverse('peminjaman:peminjaman_update', args=[peminjaman.pk]), {
            'barang': str(peminjaman.barang_id),
            'nama_peminjam': 'Nama Baru',
            'nim': 'NIM-BARU',
            'no_hp': '089999999999',
            'tanggal_pinjam': '2026-06-23',
            'tanggal_kembali': '2026-06-24',
            'status': 'diajukan',
            'catatan': 'Sesudah edit',
        })

        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        detail_list = PeminjamanAlat.objects.filter(transaksi_id=transaksi_id)
        self.assertEqual(set(detail_list.values_list('nama_peminjam', flat=True)), {'Nama Baru'})
        self.assertEqual(set(detail_list.values_list('nim', flat=True)), {'NIM-BARU'})
        self.assertEqual(set(detail_list.values_list('catatan', flat=True)), {'Sesudah edit'})
        self.assertEqual(detail_list.first().transaksi.nama_peminjam, 'Nama Baru')

    def test_admin_hapus_peminjaman_di_tabel_menghapus_semua_detail_transaksi(self):
        barang_kedua = Barang.objects.create(
            nama='Kamera Tambahan',
            kode_barang='CAM-DELETE',
            jumlah=1,
            lokasi=self.lokasi,
            kondisi='baik',
        )
        response = self.client.post(reverse('peminjaman:peminjaman_create'), {
            'selected_barang_ids': f'{self.barang.pk},{barang_kedua.pk}',
            'tanggal_pinjam': '2026-06-21',
            'tanggal_kembali': '2026-06-22',
            'catatan': 'Hapus transaksi',
        })
        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        peminjaman = PeminjamanAlat.objects.filter(nim=self.mahasiswa.nim_nik).first()
        transaksi_id = peminjaman.transaksi_id

        admin_session = self.client.session
        admin = Pengguna.objects.get(nim_nik='ADM-PJM')
        admin_session['pengguna_id'] = admin.pk
        admin_session.save()

        response = self.client.post(reverse('peminjaman:peminjaman_delete', args=[peminjaman.pk]))

        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        self.assertFalse(PeminjamanAlat.objects.filter(transaksi_id=transaksi_id).exists())
        self.assertFalse(PeminjamanTransaksi.objects.filter(pk=transaksi_id).exists())

    def test_admin_bulk_status_tidak_menampilkan_opsi_ditolak(self):
        admin_session = self.client.session
        admin = Pengguna.objects.get(nim_nik='ADM-PJM')
        admin_session['pengguna_id'] = admin.pk
        admin_session.save()

        response = self.client.get(reverse('peminjaman:peminjaman_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<option value="ditolak">Ditolak</option>', html=True)

    def test_admin_melihat_aksi_edit_dan_hapus_pengajuan_di_tabel(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti Aminah',
            nim=self.mahasiswa.nim_nik,
            no_hp=self.mahasiswa.no_hp,
            tanggal_pinjam=date(2026, 6, 21),
            tanggal_kembali=date(2026, 6, 22),
            status='diajukan',
        )
        admin_session = self.client.session
        admin = Pengguna.objects.get(nim_nik='ADM-PJM')
        admin_session['pengguna_id'] = admin.pk
        admin_session.save()

        response = self.client.get(reverse('peminjaman:peminjaman_list'))

        self.assertContains(response, reverse('peminjaman:peminjaman_update', args=[peminjaman.pk]))
        self.assertContains(response, reverse('peminjaman:peminjaman_delete', args=[peminjaman.pk]))
        self.assertContains(response, '<span>Edit</span>', html=True)
        self.assertContains(response, '<span>Hapus</span>', html=True)

    def test_mahasiswa_tidak_bisa_bulk_update_status(self):
        response = self.client.post(reverse('peminjaman:peminjaman_bulk_update'), {
            'transaksi_ids': ['1'],
            'status': 'dipinjam',
        })

        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))

    def test_peminjaman_paket_ditolak_jika_stok_item_tidak_cukup(self):
        inventaris_kamera = InventarisBarang.objects.create(nama='Kamera Terbatas', jumlah=1)
        kamera = Barang.objects.create(inventaris=inventaris_kamera, nama='Kamera Terbatas', jumlah=1, lokasi=self.lokasi)
        PeminjamanAlat.objects.create(
            barang=kamera,
            nama_peminjam='User Lama',
            nim='2201999',
            tanggal_pinjam=date(2026, 6, 20),
            tanggal_kembali=date(2026, 6, 21),
            status='dipinjam',
        )
        paket = PaketBarang.objects.create(nama='Paket Tidak Cukup')
        PaketBarangItem.objects.create(paket=paket, inventaris=inventaris_kamera, jumlah=1)

        response = self.client.post(
            reverse('peminjaman:peminjaman_create'),
            {
                'paket': str(paket.pk),
                'tanggal_pinjam': '2026-06-21',
                'tanggal_kembali': '2026-06-22',
                'status': 'dipinjam',
                'catatan': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Stok paket tidak mencukupi')
        self.assertEqual(PeminjamanAlat.objects.filter(paket=paket).count(), 0)

    def test_form_mahasiswa_tidak_menampilkan_input_identitas(self):
        response = self.client.get(reverse('peminjaman:peminjaman_create'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'type="text" name="nama_peminjam"')
        self.assertNotContains(response, 'type="text" name="nim"')
        self.assertNotContains(response, 'type="text" name="no_hp"')

    def test_form_peminjaman_menyembunyikan_pilihan_paket(self):
        response = self.client.get(reverse('peminjaman:peminjaman_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-barang-manual-section')
        self.assertNotContains(response, 'data-paket-select')
        self.assertNotContains(response, 'data-paket-manual-message')
        self.assertNotContains(response, 'Tidak memakai paket')

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

    def test_mahasiswa_hanya_melihat_daftar_dan_detail_milik_sendiri(self):
        milik_sendiri = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam=self.mahasiswa.nama_pengguna,
            nim=self.mahasiswa.nim_nik,
            no_hp=self.mahasiswa.no_hp,
            tanggal_pinjam=date(2026, 6, 21),
            tanggal_kembali=date(2026, 6, 22),
            status='diajukan',
        )
        barang_lain = Barang.objects.create(
            nama='Laptop',
            kode_barang='LAB-011',
            jumlah=1,
            lokasi=self.lokasi,
            kondisi='baik',
        )
        milik_orang_lain = PeminjamanAlat.objects.create(
            barang=barang_lain,
            nama_peminjam='Budi',
            nim='2201003',
            no_hp='081299999999',
            tanggal_pinjam=date(2026, 6, 21),
            tanggal_kembali=date(2026, 6, 22),
            status='diajukan',
        )

        list_response = self.client.get(reverse('peminjaman:peminjaman_list'))
        own_detail_response = self.client.get(reverse('peminjaman:peminjaman_detail', args=[milik_sendiri.pk]))
        other_detail_response = self.client.get(reverse('peminjaman:peminjaman_detail', args=[milik_orang_lain.pk]))

        self.assertContains(list_response, self.mahasiswa.nama_pengguna)
        self.assertNotContains(list_response, '081299999999')
        self.assertEqual(own_detail_response.status_code, 200)
        self.assertEqual(other_detail_response.status_code, 200)
        self.assertNotContains(other_detail_response, reverse('peminjaman:peminjaman_update', args=[milik_orang_lain.pk]))
        self.assertNotContains(other_detail_response, reverse('peminjaman:peminjaman_delete', args=[milik_orang_lain.pk]))

    def test_mahasiswa_melihat_tombol_edit_hapus_di_detail_pengajuan_miliknya(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti Aminah',
            nim='2201002',
            no_hp='081111111111',
            tanggal_pinjam=date(2026, 6, 21),
            tanggal_kembali=date(2026, 6, 22),
            status='diajukan',
        )

        response = self.client.get(reverse('peminjaman:peminjaman_detail', args=[peminjaman.pk]))

        self.assertContains(response, reverse('peminjaman:peminjaman_update', args=[peminjaman.pk]))
        self.assertContains(response, reverse('peminjaman:peminjaman_delete', args=[peminjaman.pk]))

    def test_asisten_lab_tidak_melihat_tombol_edit_hapus_di_detail_peminjaman_orang_lain(self):
        self.mahasiswa.role = 'asisten_lab'
        self.mahasiswa.save(update_fields=['role'])
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            nim='2201003',
            no_hp='081222222222',
            tanggal_pinjam=date(2026, 6, 21),
            tanggal_kembali=date(2026, 6, 22),
            status='diajukan',
        )

        response = self.client.get(reverse('peminjaman:peminjaman_detail', args=[peminjaman.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('peminjaman:peminjaman_update', args=[peminjaman.pk]))
        self.assertNotContains(response, reverse('peminjaman:peminjaman_delete', args=[peminjaman.pk]))

    def test_mahasiswa_tidak_melihat_form_ubah_status_detail_peminjaman(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam=self.mahasiswa.nama_pengguna,
            nim=self.mahasiswa.nim_nik,
            no_hp=self.mahasiswa.no_hp,
            tanggal_pinjam=date(2026, 6, 21),
            tanggal_kembali=date(2026, 6, 22),
            status='dipinjam',
        )

        response = self.client.get(reverse('peminjaman:peminjaman_detail', args=[peminjaman.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('peminjaman:peminjaman_detail_status_update', args=[peminjaman.pk]))
        self.assertNotContains(response, 'name="status"')

    def test_mahasiswa_tidak_bisa_memproses_status_peminjaman(self):
        endpoints = [
            'dashboard:peminjaman_accept',
            'dashboard:peminjaman_reject',
        ]
        for endpoint in endpoints:
            peminjaman = PeminjamanAlat.objects.create(
                barang=self.barang,
                nama_peminjam=self.mahasiswa.nama_pengguna,
                nim=self.mahasiswa.nim_nik,
                tanggal_pinjam=date(2026, 6, 21),
                tanggal_kembali=date(2026, 6, 22),
                status='diajukan',
            )

            response = self.client.post(reverse(endpoint, args=[peminjaman.pk]))
            peminjaman.refresh_from_db()

            self.assertRedirects(response, reverse('dashboard:home'))
            self.assertEqual(peminjaman.status, 'diajukan')
            peminjaman.delete()

    def test_mahasiswa_tidak_bisa_mengubah_status_peminjaman_aktif(self):
        endpoint_names = [
            'dashboard:peminjaman_returned',
            'dashboard:peminjaman_lost',
            'dashboard:peminjaman_broken',
        ]
        for endpoint_name in endpoint_names:
            peminjaman = PeminjamanAlat.objects.create(
                barang=self.barang,
                nama_peminjam=self.mahasiswa.nama_pengguna,
                nim=self.mahasiswa.nim_nik,
                tanggal_pinjam=date(2026, 6, 21),
                tanggal_kembali=date(2026, 6, 22),
                status='dipinjam',
            )

            response = self.client.post(reverse(endpoint_name, args=[peminjaman.pk]))
            peminjaman.refresh_from_db()

            self.assertRedirects(response, reverse('dashboard:home'))
            self.assertEqual(peminjaman.status, 'dipinjam')
            peminjaman.delete()

        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam=self.mahasiswa.nama_pengguna,
            nim=self.mahasiswa.nim_nik,
            tanggal_pinjam=date(2026, 6, 21),
            tanggal_kembali=date(2026, 6, 22),
            status='rusak',
        )

        response = self.client.post(reverse('dashboard:peminjaman_replaced', args=[peminjaman.pk]))
        peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(peminjaman.status, 'rusak')

    def test_create_mengabaikan_id_barang_duplikat_dan_invalid(self):
        response = self.client.post(
            reverse('peminjaman:peminjaman_create'),
            {
                'selected_barang_ids': f'{self.barang.pk},{self.barang.pk},invalid',
                'tanggal_pinjam': '2026-06-21',
                'tanggal_kembali': '2026-06-22',
                'catatan': '',
            },
        )

        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        self.assertEqual(PeminjamanAlat.objects.filter(barang=self.barang).count(), 1)

    def test_asisten_lab_melihat_indikator_riwayat_pribadi(self):
        self.mahasiswa.role = 'asisten_lab'
        self.mahasiswa.save(update_fields=['role'])

        response = self.client.get(reverse('peminjaman:peminjaman_list'))

        self.assertContains(response, 'Menampilkan riwayat peminjaman Anda')

    def test_asisten_lab_melihat_riwayat_peminjaman_milik_saya_setelah_dikembalikan(self):
        asisten = Pengguna.objects.create(
            nama_pengguna='Siti Asisten',
            nim_nik='2202001',
            email='siti.asisten@trisakti.ac.id',
            password='rahasia123',
            no_hp='081222222222',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
            is_verified=True,
        )
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam=asisten.nama_pengguna,
            nim=asisten.nim_nik,
            no_hp=asisten.no_hp,
            tanggal_pinjam=date(2026, 6, 18),
            tanggal_kembali=date(2026, 6, 20),
            status='dikembalikan',
        )
        session = self.client.session
        session['pengguna_id'] = asisten.pk
        session.save()

        response = self.client.get(reverse('peminjaman:peminjaman_list'), {'milik_saya': '1'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Siti Asisten')
        self.assertContains(response, 'Dikembalikan')


class PeminjamanAlatModelTests(TestCase):
    def test_kode_pinjam_dibuat_dari_tanggal_pinjam_dan_id_transaksi(self):
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

        self.assertEqual(peminjaman.kode_pinjam, f'PJM-260622-{peminjaman.transaksi_id:04d}')
