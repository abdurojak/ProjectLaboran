from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.asleb.models import Asleb, HonorAsleb
from apps.inventaris.models import Barang
from apps.jadwal.models import JadwalPraktikum
from apps.kalender.models import KegiatanKalender
from apps.peminjaman.models import PeminjamanAlat
from apps.pendaftaran_asleb.models import PengaturanPendaftaranAsleb
from apps.pendaftaran_asleb.utils import get_public_registration_url
from apps.pengguna.models import Pengguna


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
        pending_section = content.split('Peminjaman Alat Diajukan', 1)[1].split('Barang Yang Dipinjam', 1)[0]

        self.assertNotIn('data-confirm-message', pending_section)

    def test_accept_pending_peminjaman_changes_status_to_dipinjam(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        response = self.client.post(reverse('dashboard:peminjaman_accept', args=[peminjaman.pk]))
        peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(peminjaman.status, 'dipinjam')

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

    def test_reject_pending_peminjaman_deletes_record(self):
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

    def test_dashboard_shows_replacement_action_for_lost_or_broken_peminjaman(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='hilang',
        )

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'Peminjaman Perlu Diganti')
        self.assertContains(response, 'Hilang')
        self.assertContains(response, 'Digantikan')

    def test_dashboard_shows_borrowed_peminjaman_actions(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'Barang Yang Dipinjam')
        self.assertContains(response, 'Siti')
        self.assertContains(response, 'Dikembalikan')
        self.assertContains(response, 'Hilang')
        self.assertContains(response, 'Rusak')

    def test_borrowed_and_replacement_actions_use_confirmation(self):
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

        self.assertContains(response, 'data-confirm-message="', count=4)
        self.assertContains(response, 'data-confirmation-modal')
        self.assertNotContains(response, 'window.confirm')
        self.assertContains(response, 'Yakin tandai peminjaman ini sudah dikembalikan?')
        self.assertContains(response, 'Yakin tandai barang ini hilang?')
        self.assertContains(response, 'Yakin tandai barang ini rusak?')
        self.assertContains(response, 'Yakin tandai barang ini sudah digantikan?')

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

    def test_delete_active_peminjaman_makes_barang_available_again(self):
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
        self.assertFalse(PeminjamanAlat.objects.filter(pk=peminjaman.pk).exists())
        self.assertFalse(self.barang.sedang_dipinjam)
        self.assertEqual(self.barang.status_pinjam, 'Tersedia')
        self.assertEqual(self.barang.stok_tersedia, self.barang.jumlah)

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

        self.assertContains(response, 'Pendaftaran asleb sedang dibuka')
        self.assertContains(response, 'QR pendaftaran asleb')
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

        self.assertNotContains(response, 'Pendaftaran asleb sedang dibuka')
        self.assertNotContains(response, 'QR pendaftaran asleb')

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
        self.assertNotContains(response, 'Data Asleb')
        self.assertNotContains(response, 'Pendaftaran Asleb')
