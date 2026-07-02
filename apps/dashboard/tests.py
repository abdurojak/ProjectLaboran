from datetime import time

from django.test import TestCase
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.asleb.models import Asleb, HonorAsleb
from apps.inventaris.models import Barang
from apps.jadwal.models import JadwalPraktikum
from apps.kalender.models import KegiatanKalender
from apps.peminjaman.models import PeminjamanAlat, PeminjamanTransaksi
from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb
from apps.pendaftaran_asleb.utils import get_public_registration_url
from apps.pengguna.models import Pengguna
from apps.ruangan.models import RuanganLab


class DashboardViewTests(TestCase):
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
        self.barang = Barang.objects.create(nama='Mikroskop', jumlah=5)

    def test_dashboard_page_loads(self):
        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'LabHub')
        self.assertContains(response, 'dashboard-page')
        self.assertContains(response, 'dashboard-table-card')
        self.assertContains(response, 'dashboard-table-scroll')
        self.assertContains(response, '.dashboard-page .surface-card')
        self.assertContains(response, 'html[data-theme="dark"] .dashboard-page .surface-card')
        self.assertContains(response, '.dashboard-page .dashboard-table-card .dashboard-table-scroll')
        self.assertContains(response, 'background: rgba(15, 23, 42, 0.24) !important;')
        self.assertContains(response, 'background: rgba(255, 255, 255, 0.50) !important;')
        self.assertContains(response, 'background: rgba(15, 23, 42, 0.30) !important;')
        self.assertContains(response, 'background-color: rgba(15, 23, 42, 0.40) !important;')
        self.assertContains(response, 'backdrop-filter: blur(18px) saturate(1.18);')
        self.assertContains(response, '-webkit-backdrop-filter: blur(18px) saturate(1.18);')
        self.assertContains(response, 'border-color: rgba(71, 85, 105, 0.40) !important;')
        self.assertContains(response, 'scrollbar-color: rgba(71, 85, 105, 0.76) rgba(15, 23, 42, 0.58);')

    def test_sidebar_laboran_mengelompokkan_menu_barang(self):
        response = self.client.get(reverse('dashboard:home'))

        group = next(link for link in response.context['sidebar_links'] if link['title'] == 'Barang & Peminjaman')
        self.assertEqual(
            [child['title'] for child in group['children']],
            ['Inventaris', 'Barang Tertinggal', 'Peminjaman Alat'],
        )
        settings_link = next(link for link in response.context['sidebar_links'] if link['title'] == 'Pengaturan')
        self.assertNotIn('children', settings_link)
        self.assertNotContains(response, 'Master Akademik')

    def test_master_akademik_admin_hanya_muncul_di_halaman_pengaturan(self):
        self.pengguna.role = 'admin'
        self.pengguna.save(update_fields=['role'])

        response = self.client.get(reverse('dashboard:home'))

        self.assertNotContains(response, 'Master Akademik')
        settings_link = next(link for link in response.context['sidebar_links'] if link['title'] == 'Pengaturan')
        self.assertNotIn('children', settings_link)
        settings_response = self.client.get(reverse('core:settings'))
        self.assertContains(settings_response, 'Master Akademik')

    def test_dashboard_shows_pending_peminjaman(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'Peminjaman Alat Diajukan')
        self.assertContains(response, 'Budi')
        self.assertContains(response, 'Terima')
        self.assertContains(response, 'Tolak')

    def test_dashboard_mengelompokkan_peminjaman_per_kode_transaksi(self):
        barang_kedua = Barang.objects.create(nama='Kamera', jumlah=1)
        transaksi = PeminjamanTransaksi.objects.create(
            nama_peminjam='Budi',
            nim='2201002',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
        )
        PeminjamanAlat.objects.create(
            transaksi=transaksi,
            barang=self.barang,
            kode_pinjam=transaksi.kode_pinjam,
            nama_peminjam='Budi',
            nim='2201002',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )
        PeminjamanAlat.objects.create(
            transaksi=transaksi,
            barang=barang_kedua,
            kode_pinjam=transaksi.kode_pinjam,
            nama_peminjam='Budi',
            nim='2201002',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(len(response.context['peminjaman_diajukan']), 1)
        self.assertContains(response, '2 barang dalam transaksi ini')

    def test_pending_peminjaman_actions_do_not_use_confirmation(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        response = self.client.get(reverse('dashboard:home'))
        content = response.content.decode()
        pending_section = content.split('Peminjaman Alat Diajukan', 1)[1].split('Pengajuan Jadwal Praktikum', 1)[0]

        self.assertNotIn('data-confirm-message', pending_section)

    def test_accept_pending_peminjaman_changes_status_to_dipinjam(self):
        Pengguna.objects.create(
            nama_pengguna='Budi',
            nim_nik='2201002',
            email='budi@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567890',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            nim='2201002',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        response = self.client.post(reverse('dashboard:peminjaman_accept', args=[peminjaman.pk]))
        peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(peminjaman.status, 'dipinjam')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Peminjaman Alat Disetujui', mail.outbox[0].subject)

    def test_accept_pending_peminjaman_rejects_when_stock_is_no_longer_available(self):
        barang = Barang.objects.create(nama='Proyektor', jumlah=1)
        accepted = PeminjamanAlat.objects.create(
            barang=barang,
            nama_peminjam='Budi',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )
        waiting = PeminjamanAlat.objects.create(
            barang=barang,
            nama_peminjam='Siti',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        self.client.post(reverse('dashboard:peminjaman_accept', args=[accepted.pk]))
        response = self.client.post(reverse('dashboard:peminjaman_accept', args=[waiting.pk]), follow=True)
        waiting.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(waiting.status, 'diajukan')
        self.assertEqual(barang.stok_tersedia, 0)
        self.assertContains(response, 'Proyektor sedang dipinjam.')

    def test_reject_pending_peminjaman_deletes_history(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        response = self.client.post(reverse('dashboard:peminjaman_reject', args=[peminjaman.pk]))

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertFalse(PeminjamanAlat.objects.filter(pk=peminjaman.pk).exists())

    def test_dashboard_shows_pending_jadwal_praktikum(self):
        ruangan = RuanganLab.objects.create(nama='Lab Dashboard', kode='LAB-DASH', kapasitas=24)
        jadwal = JadwalPraktikum.objects.create(
            mata_kuliah='Praktikum Mobile',
            kelas='TI 5A',
            ruangan=ruangan,
            pengampu='Asleb Satu',
            hari='senin',
            waktu_mulai=time(9, 0),
            waktu_selesai=time(10, 0),
            status=JadwalPraktikum.STATUS_DIAJUKAN,
        )

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'Pengajuan Jadwal Praktikum')
        self.assertContains(response, 'Praktikum Mobile')
        self.assertContains(response, reverse('dashboard:jadwal_accept', args=[jadwal.pk]))
        self.assertContains(response, reverse('dashboard:jadwal_reject', args=[jadwal.pk]))

    def test_accept_pending_jadwal_changes_status_to_diterima(self):
        ruangan = RuanganLab.objects.create(nama='Lab Terima', kode='LAB-ACC', kapasitas=24)
        jadwal = JadwalPraktikum.objects.create(
            mata_kuliah='Praktikum AI',
            kelas='TI 6A',
            ruangan=ruangan,
            pengampu='Asleb Dua',
            hari='selasa',
            waktu_mulai=time(10, 0),
            waktu_selesai=time(11, 0),
            status=JadwalPraktikum.STATUS_DIAJUKAN,
        )

        response = self.client.post(reverse('dashboard:jadwal_accept', args=[jadwal.pk]))
        jadwal.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(jadwal.status, JadwalPraktikum.STATUS_DITERIMA)

    def test_accept_pending_jadwal_rejects_when_conflicting_with_accepted_jadwal(self):
        ruangan = RuanganLab.objects.create(nama='Lab Konflik', kode='LAB-CONF', kapasitas=24)
        JadwalPraktikum.objects.create(
            mata_kuliah='Praktikum Diterima',
            kelas='TI 4A',
            ruangan=ruangan,
            pengampu='Dosen Satu',
            hari='rabu',
            waktu_mulai=time(8, 0),
            waktu_selesai=time(10, 0),
            status=JadwalPraktikum.STATUS_DITERIMA,
        )
        jadwal = JadwalPraktikum.objects.create(
            mata_kuliah='Praktikum Bentrok',
            kelas='TI 4B',
            ruangan=ruangan,
            pengampu='Asleb Dua',
            hari='rabu',
            waktu_mulai=time(9, 0),
            waktu_selesai=time(11, 0),
            status=JadwalPraktikum.STATUS_DIAJUKAN,
        )

        response = self.client.post(reverse('dashboard:jadwal_accept', args=[jadwal.pk]), follow=True)
        jadwal.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(jadwal.status, JadwalPraktikum.STATUS_DIAJUKAN)
        self.assertContains(response, 'Jadwal tidak bisa diterima karena ruangan sudah dipakai')

    def test_reject_pending_jadwal_changes_status_to_ditolak(self):
        ruangan = RuanganLab.objects.create(nama='Lab Tolak', kode='LAB-REJ', kapasitas=24)
        jadwal = JadwalPraktikum.objects.create(
            mata_kuliah='Praktikum Ditolak',
            kelas='TI 7A',
            ruangan=ruangan,
            pengampu='Asleb Tiga',
            hari='jumat',
            waktu_mulai=time(13, 0),
            waktu_selesai=time(14, 0),
            status=JadwalPraktikum.STATUS_DIAJUKAN,
        )

        response = self.client.post(reverse('dashboard:jadwal_reject', args=[jadwal.pk]))
        jadwal.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(jadwal.status, JadwalPraktikum.STATUS_DITOLAK)

    def test_dashboard_menyembunyikan_panel_penggantian_barang(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='hilang',
        )

        response = self.client.get(reverse('dashboard:home'))

        self.assertNotContains(response, 'Peminjaman Perlu Diganti')
        self.assertContains(response, reverse('peminjaman:peminjaman_list'))

    def test_dashboard_menyembunyikan_panel_barang_dipinjam(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )

        response = self.client.get(reverse('dashboard:home'))

        self.assertNotContains(response, 'Barang Yang Dipinjam')
        self.assertNotContains(response, 'Dikembalikan')

    def test_dashboard_ringkas_tidak_memuat_aksi_status_peminjaman(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='rusak',
        )

        response = self.client.get(reverse('dashboard:home'))

        self.assertNotContains(response, 'data-confirm-message="')
        self.assertContains(response, 'data-confirmation-modal')
        self.assertNotContains(response, 'window.confirm')

    def test_mark_borrowed_as_returned_changes_status_to_dikembalikan(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )

        response = self.client.post(reverse('dashboard:peminjaman_returned', args=[peminjaman.pk]))
        peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(peminjaman.status, 'dikembalikan')
        self.assertFalse(self.barang.sedang_dipinjam)
        self.assertEqual(self.barang.status_pinjam, 'Tersedia')
        self.assertEqual(self.barang.stok_tersedia, self.barang.jumlah)

    def test_mark_borrowed_as_lost_changes_status_to_hilang(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )

        response = self.client.post(reverse('dashboard:peminjaman_lost', args=[peminjaman.pk]))
        peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(peminjaman.status, 'hilang')

    def test_mark_borrowed_as_broken_changes_status_to_rusak(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )

        response = self.client.post(reverse('dashboard:peminjaman_broken', args=[peminjaman.pk]))
        peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(peminjaman.status, 'rusak')

    def test_mark_replaced_changes_lost_or_broken_status_to_digantikan(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='rusak',
        )

        response = self.client.post(reverse('dashboard:peminjaman_replaced', args=[peminjaman.pk]))
        peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(peminjaman.status, 'digantikan')
        self.assertFalse(self.barang.sedang_dipinjam)
        self.assertEqual(self.barang.status_pinjam, 'Tersedia')
        self.assertEqual(self.barang.stok_tersedia, self.barang.jumlah)

    def test_delete_active_peminjaman_is_blocked_to_preserve_history(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )

        self.assertTrue(self.barang.sedang_dipinjam)
        response = self.client.post(reverse('peminjaman:peminjaman_delete', args=[peminjaman.pk]))

        self.assertRedirects(response, reverse('peminjaman:peminjaman_list'))
        self.assertTrue(PeminjamanAlat.objects.filter(pk=peminjaman.pk).exists())
        self.assertTrue(self.barang.sedang_dipinjam)

    def test_dashboard_mahasiswa_menyembunyikan_panel_operasional_admin(self):
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
            barang=self.barang,
            nama_peminjam='Siti Aminah',
            nim='2201002',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))

        self.assertNotIn('Asisten Laboratorium', [link['title'] for link in response.context['sidebar_links']])
        self.assertContains(response, 'Peminjaman Saya')
        self.assertContains(response, 'Mikroskop')
        self.assertContains(response, 'Jadwal Praktikum')
        self.assertContains(response, 'Ruangan')
        self.assertContains(response, reverse('ruangan:ruangan_list'))
        self.assertNotContains(response, 'Peminjaman Alat Diajukan')
        self.assertNotContains(response, 'Barang Yang Dipinjam')
        self.assertNotContains(response, 'Peminjaman Perlu Diganti')
        self.assertNotContains(response, 'Inventaris Terbaru')
        self.assertNotContains(response, 'Akses Cepat')
        self.assertNotContains(response, 'Aktivitas Terbaru')

    def test_dashboard_mahasiswa_menampilkan_kalender_kegiatan_di_atas_peminjaman_saya(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Siti Aminah',
            nim_nik='2201002',
            email='siti-kalender@example.com',
            password='rahasia123',
            no_hp='081111111111',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        KegiatanKalender.objects.create(
            judul='Workshop Keamanan Data',
            tanggal=timezone.localdate(),
            waktu_mulai=timezone.datetime.strptime('08:00', '%H:%M').time(),
            waktu_selesai=timezone.datetime.strptime('10:00', '%H:%M').time(),
            lokasi='Aula Laboratorium',
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))
        content = response.content.decode()

        self.assertContains(response, 'Kalender')
        self.assertContains(response, 'Kegiatan Terdekat')
        self.assertContains(response, 'Workshop Keamanan Data')
        self.assertContains(response, 'Aula Laboratorium')
        self.assertContains(response, reverse('kalender:kegiatan_list'))
        self.assertLess(content.index('Kegiatan Terdekat'), content.index('Peminjaman Saya'))

    def test_dashboard_mahasiswa_menampilkan_peringatan_barang_bermasalah_paling_atas(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Reno Pratama',
            nim_nik='2201012',
            email='reno-dashboard@example.com',
            password='rahasia123',
            no_hp='081111111112',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        PeminjamanAlat.objects.create(
            barang=Barang.objects.create(nama='Kamera Rusak', jumlah=1),
            nama_peminjam='Reno Pratama',
            nim=mahasiswa.nim_nik,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='rusak',
        )
        PeminjamanAlat.objects.create(
            barang=Barang.objects.create(nama='Recorder Hilang', jumlah=1),
            nama_peminjam='Reno Pratama',
            nim=mahasiswa.nim_nik,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='hilang',
        )
        PeminjamanAlat.objects.create(
            barang=Barang.objects.create(nama='Tripod Terlambat', jumlah=1),
            nama_peminjam='Reno Pratama',
            nim=mahasiswa.nim_nik,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate() - timezone.timedelta(days=1),
            status='dipinjam',
        )
        PeminjamanAlat.objects.create(
            barang=Barang.objects.create(nama='Laptop Masih Aman', jumlah=1),
            nama_peminjam='Reno Pratama',
            nim=mahasiswa.nim_nik,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))
        content = response.content.decode()

        self.assertContains(response, 'Peringatan Peminjaman')
        self.assertContains(response, 'Kamera Rusak')
        self.assertContains(response, 'Recorder Hilang')
        self.assertContains(response, 'Tripod Terlambat')
        self.assertContains(response, 'Lewat masa pengembalian')
        warning_items = [item['barang'] for item in response.context['peringatan_peminjaman_saya']]
        self.assertNotIn('Laptop Masih Aman', warning_items)
        self.assertLess(content.index('Peringatan Peminjaman'), content.index('Pendaftaran Aslab') if 'Pendaftaran Aslab' in content else content.index('Kegiatan Terdekat'))

    def test_dashboard_mahasiswa_menyembunyikan_peringatan_barang_jika_tidak_ada_masalah(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Nina Putri',
            nim_nik='2201013',
            email='nina-dashboard@example.com',
            password='rahasia123',
            no_hp='081111111113',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        PeminjamanAlat.objects.create(
            barang=Barang.objects.create(nama='Barang Aman', jumlah=1),
            nama_peminjam='Nina Putri',
            nim=mahasiswa.nim_nik,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))

        self.assertNotContains(response, 'Peringatan Peminjaman')

    def test_dashboard_asisten_lab_menampilkan_peringatan_barang_paling_atas(self):
        asisten = Pengguna.objects.create(
            nama_pengguna='Aldi Asisten',
            nim_nik='2202012',
            email='aldi.asisten@example.com',
            password='rahasia123',
            no_hp='081222222212',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='asisten_lab',
        )
        PeminjamanAlat.objects.create(
            barang=Barang.objects.create(nama='Kamera Aslab', jumlah=1),
            nama_peminjam='Aldi Asisten',
            nim=asisten.nim_nik,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate() - timezone.timedelta(days=2),
            status='dipinjam',
        )
        session = self.client.session
        session['pengguna_id'] = asisten.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))
        content = response.content.decode()

        self.assertContains(response, 'Peringatan Peminjaman')
        self.assertContains(response, 'Kamera Aslab')
        self.assertContains(response, 'Honor Bulan Ini')
        self.assertLess(content.index('Peringatan Peminjaman'), content.index('Honor Bulan Ini'))

    def test_dashboard_mahasiswa_menampilkan_qr_pendaftaran_asleb_saat_dibuka(self):
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
        pengaturan = PengaturanPendaftaranAsleb.get_solo()
        pengaturan.dibuka = True
        pengaturan.save(update_fields=['dibuka'])
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'Pendaftaran aslab sedang dibuka')
        self.assertContains(response, 'QR pendaftaran aslab')
        self.assertContains(response, get_public_registration_url())

    def test_dashboard_mahasiswa_menyembunyikan_qr_pendaftaran_asleb_saat_ditutup(self):
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
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))

        self.assertNotContains(response, 'Pendaftaran aslab sedang dibuka')
        self.assertNotContains(response, 'QR pendaftaran aslab')

    def test_dashboard_asisten_lab_menampilkan_total_honor_bulan_ini(self):
        asisten = Pengguna.objects.create(
            nama_pengguna='Ricardo Dharma Saputra',
            nim_nik='20260001',
            email='ricardo.dharma@trisakti.ac.id',
            password='rahasia123',
            no_hp='',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='asisten_lab',
        )
        data_asleb = Asleb.objects.create(
            nama='Ricardo Dharma Saputra',
            nim='20260001',
            no_hp='',
            email='ricardo.dharma@trisakti.ac.id',
            program_studi='Informatika',
            matkul='Pemrograman Web',
            semester=4,
            tanggal_bergabung=timezone.localdate(),
        )
        matkul, _ = MataKuliahAsleb.objects.get_or_create(
            kode='SDA_TIF01_ABDUL',
            defaults={
                'nama': 'Struktur Data dan Algoritma',
                'dosen': 'Abdul Rois',
                'kelas': 'TIF-01',
            },
        )
        for index in range(3):
            PendaftaranAsleb.objects.create(
                nama='Ricardo Dharma Saputra',
                nim='20260001',
                no_hp='',
                email=f'ricardo{index}@std.trisakti.ac.id',
                program_studi='Informatika',
                semester=4,
                matkul=matkul,
                metode_rekening='rekening_bank',
                rekening='BCA 123456789',
                status='digenerate',
            )
        HonorAsleb.objects.create(
            asleb=data_asleb,
            bulan=timezone.localdate().replace(day=1),
            level='senior',
            jumlah_praktikum=2,
            total_pertemuan=8,
            status='diproses',
        )
        session = self.client.session
        session['pengguna_id'] = asisten.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'Honor Bulan Ini')
        self.assertContains(response, 'Rp 448.000')
        self.assertNotContains(response, 'Inventaris')
        self.assertNotContains(response, 'Data Aslab')
        self.assertNotContains(response, 'Pendaftaran Aslab')

    def test_dashboard_asisten_lab_honor_dibayar_reset_saldo_bulan_ini(self):
        asisten = Pengguna.objects.create(
            nama_pengguna='Siti Asisten',
            nim_nik='20260002',
            email='siti.asisten@trisakti.ac.id',
            password='rahasia123',
            no_hp='',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
        )
        data_asleb = Asleb.objects.create(
            nama='Siti Asisten',
            nim='20260002',
            no_hp='',
            email='siti.asisten@trisakti.ac.id',
            program_studi='Informatika',
            matkul='Pemrograman Web',
            semester=4,
            tanggal_bergabung=timezone.localdate(),
        )
        HonorAsleb.objects.create(
            asleb=data_asleb,
            bulan=timezone.localdate().replace(day=1),
            jumlah_praktikum=1,
            total_pertemuan=3,
            status='dibayar',
        )
        session = self.client.session
        session['pengguna_id'] = asisten.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'Honor Bulan Ini')
        self.assertContains(response, 'Rp 0')
        self.assertContains(response, 'Riwayat Honor Saya')
        self.assertContains(response, 'Jadwal Praktikum')
        self.assertContains(response, 'dashboard-glass-item')
        self.assertContains(response, '.dashboard-page .dashboard-glass-item')
        self.assertContains(response, 'Dibayar')

    def test_dashboard_asisten_lab_tidak_menampilkan_pendaftaran_saat_dibuka(self):
        asisten = Pengguna.objects.create(
            nama_pengguna='Ricardo Dharma Saputra',
            nim_nik='20260001',
            email='ricardo.dharma@trisakti.ac.id',
            password='rahasia123',
            no_hp='',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='asisten_lab',
        )
        pengaturan = PengaturanPendaftaranAsleb.get_solo()
        pengaturan.dibuka = True
        pengaturan.save(update_fields=['dibuka'])
        session = self.client.session
        session['pengguna_id'] = asisten.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))

        self.assertNotContains(response, 'Pendaftaran aslab sedang dibuka')
        self.assertNotContains(response, 'Buka Form Pendaftaran')
        self.assertNotContains(response, get_public_registration_url())
