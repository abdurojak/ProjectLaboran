from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from apps.pengguna.models import Pengguna
from apps.inventaris.models import Barang
from apps.peminjaman.models import PeminjamanAlat
from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb
from apps.kalender.context_processors import get_unread_notification_count, get_unread_peminjaman_notification_count

from .models import KegiatanKalender
from .utils import get_perayaan_notifications


class KalenderViewsTests(TestCase):
    def setUp(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='Lab Admin',
            nim_nik='ADM-KALENDER',
            email='admin-kalender@example.com',
            password='rahasia123',
            no_hp='081234567801',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='admin',
        )
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()

        KegiatanKalender.objects.create(
            judul='Praktikum Jaringan',
            tanggal=date.today() + timedelta(days=1),
            waktu_mulai=time(9, 0),
            waktu_selesai=time(11, 0),
            lokasi='Lab Sistem Keamanan Informasi',
            tampilkan_notifikasi=True,
        )

    def test_kalender_page_loads(self):
        response = self.client.get(reverse('kalender:kegiatan_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kalender Kegiatan')
        self.assertContains(response, 'Tambah Kegiatan')
        self.assertContains(response, 'Hari Perayaan Otomatis')
        self.assertContains(response, 'Peringatan Universitas Trisakti')
        self.assertContains(response, 'Keterangan Notifikasi')
        self.assertContains(response, 'Hari Kemerdekaan Republik Indonesia')
        self.assertContains(response, 'Tahun Baru Imlek')
        self.assertContains(response, 'Peringatan Tragedi Trisakti')
        self.assertContains(response, 'Dies Natalis Universitas Trisakti')

    def test_mahasiswa_kalender_hanya_menampilkan_agenda_terdekat(self):
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

        response = self.client.get(reverse('kalender:kegiatan_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Agenda Terdekat')
        self.assertNotContains(response, 'Tambah Kegiatan')
        self.assertNotContains(response, 'Hari Perayaan Otomatis')
        self.assertNotContains(response, 'Peringatan Universitas Trisakti')
        self.assertNotContains(response, 'Keterangan Notifikasi')

    def test_asisten_lab_kalender_sama_seperti_mahasiswa(self):
        asisten = Pengguna.objects.create(
            nama_pengguna='Asisten Lab',
            nim_nik='ASL-001',
            email='asisten@example.com',
            password='rahasia123',
            no_hp='081111111112',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='asisten_lab',
        )
        session = self.client.session
        session['pengguna_id'] = asisten.pk
        session.save()

        response = self.client.get(reverse('kalender:kegiatan_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Agenda Terdekat')
        self.assertNotContains(response, 'Tambah Kegiatan')
        self.assertNotContains(response, 'Hari Perayaan Otomatis')
        self.assertNotContains(response, 'Peringatan Universitas Trisakti')
        self.assertNotContains(response, 'Keterangan Notifikasi')

    def test_notifikasi_page_loads(self):
        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notifikasi')

    def test_notifikasi_mahasiswa_menampilkan_perubahan_status_peminjaman_saya(self):
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
        barang = Barang.objects.create(nama='Kamera', jumlah=1)
        peminjaman_saya = PeminjamanAlat.objects.create(
            barang=barang,
            nama_peminjam='Siti Aminah',
            nim='2201002',
            tanggal_pinjam=date.today(),
            tanggal_kembali=date.today(),
            status='dipinjam',
        )
        PeminjamanAlat.objects.create(
            barang=barang,
            nama_peminjam='Budi',
            nim='2201003',
            tanggal_pinjam=date.today(),
            tanggal_kembali=date.today(),
            status='dikembalikan',
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertContains(response, 'Status peminjaman Kamera: Dipinjam')
        self.assertContains(response, 'border-brand-200 bg-white ring-1 ring-brand-100')
        self.assertNotContains(response, 'Belum dibaca')
        self.assertContains(response, reverse('peminjaman:peminjaman_detail', args=[peminjaman_saya.pk]))
        self.assertNotContains(response, 'Budi')

        mahasiswa.refresh_from_db()
        self.assertIsNotNone(mahasiswa.notifikasi_dibaca_pada)

        second_response = self.client.get(reverse('kalender:notifikasi_list'))
        self.assertContains(second_response, 'Status peminjaman Kamera: Dipinjam')
        self.assertContains(second_response, 'border-slate-200 bg-slate-50/80')

    def test_unread_notification_count_menghitung_status_peminjaman_mahasiswa(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Siti Aminah',
            nim_nik='2201002',
            email='siti2@example.com',
            password='rahasia123',
            no_hp='081111111111',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        barang = Barang.objects.create(nama='Tripod', jumlah=1)
        PeminjamanAlat.objects.create(
            barang=barang,
            nama_peminjam='Siti Aminah',
            nim='2201002',
            tanggal_pinjam=date.today(),
            tanggal_kembali=date.today(),
            status='dipinjam',
        )

        self.assertEqual(get_unread_peminjaman_notification_count(mahasiswa), 1)

        mahasiswa.notifikasi_dibaca_pada = timezone.now()
        mahasiswa.save(update_fields=['notifikasi_dibaca_pada'])

        self.assertEqual(get_unread_peminjaman_notification_count(mahasiswa), 0)

    def test_notifikasi_mahasiswa_menampilkan_pendaftaran_aslab_saat_dibuka(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Ari Mahendra',
            nim_nik='2201004',
            email='ari@example.com',
            password='rahasia123',
            no_hp='081111111114',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        pengaturan = PengaturanPendaftaranAsleb.get_solo()
        pengaturan.dibuka = True
        pengaturan.save(update_fields=['dibuka', 'diperbarui_pada'])
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        self.assertEqual(get_unread_notification_count(mahasiswa), 1)

        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertContains(response, 'Pendaftaran aslab sedang dibuka')
        self.assertContains(response, reverse('pendaftaran_asleb:pendaftaran_public'))
        self.assertContains(response, 'border-brand-200 bg-white ring-1 ring-brand-100')

        mahasiswa.refresh_from_db()
        self.assertEqual(get_unread_notification_count(mahasiswa), 0)

        second_response = self.client.get(reverse('kalender:notifikasi_list'))
        self.assertContains(second_response, 'Pendaftaran aslab sedang dibuka')
        self.assertContains(second_response, 'border-slate-200 bg-slate-50/80')

    def test_notifikasi_mahasiswa_menampilkan_pendaftaran_aslab_saat_ditutup(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Nadia Putri',
            nim_nik='2201005',
            email='nadia@example.com',
            password='rahasia123',
            no_hp='081111111115',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        pengaturan = PengaturanPendaftaranAsleb.get_solo()
        pengaturan.dibuka = False
        pengaturan.save(update_fields=['dibuka', 'diperbarui_pada'])
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        self.assertEqual(get_unread_notification_count(mahasiswa), 1)

        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertContains(response, 'Pendaftaran aslab sudah ditutup')
        self.assertContains(response, 'Form pendaftaran asisten laboratorium sudah ditutup')
        self.assertContains(response, 'Ditutup')
        self.assertContains(response, 'border-brand-200 bg-white ring-1 ring-brand-100')

        mahasiswa.refresh_from_db()
        self.assertEqual(get_unread_notification_count(mahasiswa), 0)

    def test_notifikasi_mahasiswa_menampilkan_pendaftaran_aslab_saya_yang_diterima(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Dina Maharani',
            nim_nik='2201007',
            email='dina@example.com',
            password='rahasia123',
            no_hp='081111111117',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        matkul = MataKuliahAsleb.objects.create(
            kode='SDA_TEST',
            nama='Struktur Data',
            dosen='Dosen Test',
            kelas='TIF-01',
        )
        PendaftaranAsleb.objects.create(
            nama='Dina Maharani',
            nim='2201007',
            no_hp='081111111117',
            email='dina@example.com',
            program_studi='Informatika',
            semester=4,
            matkul=matkul,
            status='diterima',
        )
        PendaftaranAsleb.objects.create(
            nama='Mahasiswa Lain',
            nim='2201999',
            no_hp='081111119999',
            email='lain@example.com',
            program_studi='Informatika',
            semester=4,
            matkul=matkul,
            status='diterima',
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        self.assertGreaterEqual(get_unread_notification_count(mahasiswa), 1)

        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertContains(response, 'Pendaftaran aslab Anda diterima')
        self.assertContains(response, 'Struktur Data')
        self.assertContains(response, 'Diterima')
        self.assertNotContains(response, 'Mahasiswa Lain')

        mahasiswa.refresh_from_db()
        self.assertEqual(get_unread_notification_count(mahasiswa), 0)

    def test_notifikasi_mahasiswa_ditampilkan_per_20_dengan_tombol_lainnya(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Raka Saputra',
            nim_nik='2201006',
            email='raka@example.com',
            password='rahasia123',
            no_hp='081111111116',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        barang = Barang.objects.create(nama='Kit Praktikum', jumlah=30)
        for index in range(25):
            PeminjamanAlat.objects.create(
                barang=barang,
                nama_peminjam='Raka Saputra',
                nim='2201006',
                tanggal_pinjam=date.today() - timedelta(days=index),
                tanggal_kembali=date.today(),
                status='dipinjam',
            )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertEqual(len(response.context['notifikasi_list']), 20)
        self.assertContains(response, 'Tampilkan lainnya')
        self.assertContains(response, '?page=2')

        second_response = self.client.get(reverse('kalender:notifikasi_list'), {'page': 2})

        self.assertGreater(len(second_response.context['notifikasi_list']), 0)
        self.assertLessEqual(len(second_response.context['notifikasi_list']), 20)
        self.assertNotContains(second_response, '?page=3')

    def test_perayaan_otomatis_masuk_notifikasi(self):
        notifications = get_perayaan_notifications(date(2026, 8, 15), days=7)

        titles = [notification['judul'] for notification in notifications]
        self.assertIn('Hari Kemerdekaan Republik Indonesia', titles)


