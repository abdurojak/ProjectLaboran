from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from apps.asleb.models import Asleb
from apps.pengguna.models import Pengguna
from apps.inventaris.models import Barang
from apps.peminjaman.models import PeminjamanAlat
from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb
from apps.kalender.context_processors import get_unread_notification_count, get_unread_peminjaman_notification_count
from apps.jadwal.models import JadwalPraktikum
from apps.ruangan.models import RuanganLab

from .models import KegiatanKalender, Notifikasi
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
        self.barang = Barang.objects.create(nama='Kamera', kode_barang='CAM-001', jumlah=1, kondisi='baik')

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
        self.assertContains(response, 'Tambah Kegiatan')
        self.assertContains(response, 'Kegiatan Pribadi')
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
        self.assertContains(response, 'Tambah Kegiatan')
        self.assertContains(response, 'Jadwal Praktikum Saya')
        self.assertNotContains(response, 'Hari Perayaan Otomatis')
        self.assertNotContains(response, 'Peringatan Universitas Trisakti')
        self.assertNotContains(response, 'Keterangan Notifikasi')

    def test_admin_bisa_share_kegiatan_ke_role_tertentu(self):
        response = self.client.post(reverse('kalender:kegiatan_create'), {
            'judul': 'Briefing Praktikum',
            'tanggal': date.today() + timedelta(days=2),
            'waktu_mulai': '09:00',
            'waktu_selesai': '10:00',
            'lokasi': 'Lab Pemrograman',
            'deskripsi': 'Briefing untuk asisten lab.',
            'tampilkan_notifikasi': 'on',
            'target_role': ['asisten_lab', 'laboran'],
        })

        self.assertRedirects(response, reverse('kalender:kegiatan_list'))
        kegiatan = KegiatanKalender.objects.get(judul='Briefing Praktikum')
        self.assertEqual(kegiatan.target_role_list, ['asisten_lab', 'laboran'])
        self.assertEqual(kegiatan.target_role_display, 'Asisten Lab, Laboran')

    def test_mahasiswa_membuat_kegiatan_pribadi(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Siti Aminah',
            nim_nik='2201002',
            email='siti.private@example.com',
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

        response = self.client.post(reverse('kalender:kegiatan_create'), {
            'judul': 'Belajar Struktur Data',
            'tanggal': date.today() + timedelta(days=2),
            'waktu_mulai': '19:00',
            'waktu_selesai': '20:00',
            'lokasi': 'Rumah',
            'deskripsi': 'Catatan pribadi.',
            'tampilkan_notifikasi': 'on',
            'target_role': ['admin', 'laboran', 'mahasiswa'],
        })

        self.assertRedirects(response, reverse('kalender:kegiatan_list'))
        kegiatan = KegiatanKalender.objects.get(judul='Belajar Struktur Data')
        self.assertEqual(kegiatan.dibuat_oleh, mahasiswa)
        self.assertEqual(kegiatan.target_role, '')

    def test_mahasiswa_tidak_melihat_kegiatan_pribadi_mahasiswa_lain(self):
        pemilik = Pengguna.objects.create(
            nama_pengguna='Pemilik Agenda',
            nim_nik='2201010',
            email='pemilik@example.com',
            password='rahasia123',
            no_hp='081111111110',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        penonton = Pengguna.objects.create(
            nama_pengguna='Penonton Agenda',
            nim_nik='2201011',
            email='penonton@example.com',
            password='rahasia123',
            no_hp='081111111119',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        KegiatanKalender.objects.create(
            judul='Agenda Pribadi Pemilik',
            tanggal=date.today() + timedelta(days=3),
            waktu_mulai=time(8, 0),
            dibuat_oleh=pemilik,
        )
        KegiatanKalender.objects.create(
            judul='Pengumuman Untuk Mahasiswa',
            tanggal=date.today() + timedelta(days=3),
            waktu_mulai=time(9, 0),
            target_role='mahasiswa',
        )
        session = self.client.session
        session['pengguna_id'] = penonton.pk
        session.save()

        response = self.client.get(reverse('kalender:kegiatan_list'))

        self.assertNotContains(response, 'Agenda Pribadi Pemilik')
        self.assertContains(response, 'Pengumuman Untuk Mahasiswa')

    def test_jadwal_praktikum_asisten_lab_muncul_di_ringkasan_saya_saja(self):
        asisten = Pengguna.objects.create(
            nama_pengguna='Asisten SDA',
            nim_nik='2202001',
            email='asisten.sda@example.com',
            password='rahasia123',
            no_hp='081222222222',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='asisten_lab',
        )
        Asleb.objects.create(
            nama='Asisten SDA',
            nim='2202001',
            no_hp='081222222222',
            email='asisten.sda@example.com',
            program_studi='Informatika',
            matkul='Struktur Data dan Algoritma - Abdul Roohman, M.Kom - TIF-01',
            semester=5,
            tanggal_bergabung=date.today(),
        )
        ruangan = RuanganLab.objects.create(
            nama='Lab Pemrograman',
            kode='LAB-PROG-KAL',
            kapasitas=39,
            warna='blue',
        )
        JadwalPraktikum.objects.create(
            mata_kuliah='Struktur Data dan Algoritma',
            kelas='TIF-01',
            ruangan=ruangan,
            pengampu='Abdul Roohman, M.Kom',
            hari='senin',
            waktu_mulai=time(10, 0),
            waktu_selesai=time(12, 0),
        )
        session = self.client.session
        session['pengguna_id'] = asisten.pk
        session.save()

        response = self.client.get(reverse('kalender:kegiatan_list'))

        event_titles = [event['title'] for event in response.context['calendar_events']]
        self.assertNotIn('Praktikum Struktur Data dan Algoritma - TIF-01', event_titles)
        self.assertContains(response, 'Jadwal Praktikum Saya')
        self.assertContains(response, 'Struktur Data dan Algoritma - TIF-01')

    def test_jadwal_praktikum_tidak_muncul_sebagai_event_kalender_global(self):
        ruangan = RuanganLab.objects.create(
            nama='Lab Kalender Global',
            kode='LAB-KAL-GLOBAL',
            kapasitas=24,
            warna='teal',
        )
        JadwalPraktikum.objects.create(
            mata_kuliah='Pemrograman Web',
            kelas='TIF-02',
            ruangan=ruangan,
            pengampu='Pak Global',
            hari='rabu',
            waktu_mulai=time(13, 0),
            waktu_selesai=time(15, 0),
            status=JadwalPraktikum.STATUS_DIAJUKAN,
        )
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Global',
            nim_nik='2201099',
            email='mahasiswa-global@example.com',
            password='rahasia123',
            no_hp='081111111113',
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

        event_titles = [event['title'] for event in response.context['calendar_events']]
        self.assertNotIn('Praktikum Pemrograman Web - TIF-02', event_titles)
        self.assertNotContains(response, 'Jadwal Praktikum Otomatis')
        self.assertNotContains(response, 'Pemrograman Web - TIF-02')

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

    def test_notifikasi_disimpan_di_tabel_dan_diurutkan_terbaru(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Siti Aminah',
            nim_nik='2201002',
            email='siti.order@example.com',
            password='rahasia123',
            no_hp='081111111111',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        barang_lama = Barang.objects.create(nama='Kamera Lama', jumlah=1)
        barang_baru = Barang.objects.create(nama='Kamera Baru', jumlah=1)
        PeminjamanAlat.objects.create(
            barang=barang_lama,
            nama_peminjam='Siti Aminah',
            nim=mahasiswa.nim_nik,
            tanggal_pinjam=date.today(),
            tanggal_kembali=date.today(),
            status='dipinjam',
        )
        PeminjamanAlat.objects.create(
            barang=barang_baru,
            nama_peminjam='Siti Aminah',
            nim=mahasiswa.nim_nik,
            tanggal_pinjam=date.today(),
            tanggal_kembali=date.today(),
            status='rusak',
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertGreaterEqual(Notifikasi.objects.filter(pengguna=mahasiswa).count(), 2)
        titles = [notifikasi.judul for notifikasi in response.context['notifikasi_list']]
        self.assertLess(
            titles.index('Status peminjaman Kamera Baru: Rusak'),
            titles.index('Status peminjaman Kamera Lama: Dipinjam'),
        )

    def test_notifikasi_admin_menampilkan_pengajuan_peminjaman_baru(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            nim='2201002',
            no_hp='081234567890',
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pengajuan peminjaman baru: Kamera')
        self.assertContains(response, 'Budi mengajukan peminjaman alat')

    def test_notifikasi_asisten_lab_menampilkan_status_peminjaman_saya(self):
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
            nama_peminjam='Siti Asisten',
            nim=asisten.nim_nik,
            no_hp=asisten.no_hp,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )
        session = self.client.session
        session['pengguna_id'] = asisten.pk
        session.save()

        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Status peminjaman Kamera: Dipinjam')

    def test_notifikasi_asisten_lab_menampilkan_jadwal_praktikum_diterima(self):
        asisten = Pengguna.objects.create(
            nama_pengguna='Siti Asisten',
            nim_nik='2202002',
            email='siti.jadwal@trisakti.ac.id',
            password='rahasia123',
            no_hp='081222222223',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
            is_verified=True,
        )
        matkul = MataKuliahAsleb.objects.create(
            kode='PBO_JADWAL_TEST',
            nama='Pemrograman Berorientasi Objek',
            dosen='Dosen Test',
            kelas='TIF-01',
        )
        PendaftaranAsleb.objects.create(
            nama='Siti Asisten',
            nim=asisten.nim_nik,
            no_hp=asisten.no_hp,
            email=asisten.email,
            program_studi='Informatika',
            semester=4,
            matkul=matkul,
            status='digenerate',
        )
        ruangan = RuanganLab.objects.create(kode='LAB-JADWAL-NOTIF', nama='Lab Notifikasi Jadwal')
        JadwalPraktikum.objects.create(
            mata_kuliah=str(matkul),
            kelas=matkul.kelas,
            ruangan=ruangan,
            pengampu=matkul.dosen,
            hari='senin',
            waktu_mulai=time(9, 0),
            waktu_selesai=time(10, 30),
            status=JadwalPraktikum.STATUS_DITERIMA,
        )
        session = self.client.session
        session['pengguna_id'] = asisten.pk
        session.save()

        self.assertGreaterEqual(get_unread_notification_count(asisten), 1)

        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jadwal praktikum Anda diterima')
        self.assertContains(response, 'Pemrograman Berorientasi Objek')
        self.assertContains(response, 'Senin, 09:00-10:30')
        self.assertContains(response, 'Lab Notifikasi Jadwal')

        asisten.refresh_from_db()
        self.assertEqual(get_unread_notification_count(asisten), 0)

    def test_notifikasi_asisten_lab_menampilkan_jadwal_praktikum_ditolak(self):
        asisten = Pengguna.objects.create(
            nama_pengguna='Rani Asisten',
            nim_nik='2202003',
            email='rani.jadwal@trisakti.ac.id',
            password='rahasia123',
            no_hp='081222222224',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
            is_verified=True,
        )
        matkul = MataKuliahAsleb.objects.create(
            kode='PBO_JADWAL_TOLAK_TEST',
            nama='Pemrograman Berorientasi Objek',
            dosen='Dosen Test',
            kelas='TIF-02',
        )
        PendaftaranAsleb.objects.create(
            nama='Rani Asisten',
            nim=asisten.nim_nik,
            no_hp=asisten.no_hp,
            email=asisten.email,
            program_studi='Informatika',
            semester=4,
            matkul=matkul,
            status='digenerate',
        )
        ruangan = RuanganLab.objects.create(kode='LAB-JADWAL-TOLAK', nama='Lab Jadwal Ditolak')
        JadwalPraktikum.objects.create(
            mata_kuliah=str(matkul),
            kelas=matkul.kelas,
            ruangan=ruangan,
            pengampu=matkul.dosen,
            hari='rabu',
            waktu_mulai=time(13, 0),
            waktu_selesai=time(14, 30),
            status=JadwalPraktikum.STATUS_DITOLAK,
        )
        session = self.client.session
        session['pengguna_id'] = asisten.pk
        session.save()

        self.assertGreaterEqual(get_unread_notification_count(asisten), 1)

        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jadwal praktikum Anda ditolak')
        self.assertContains(response, 'Pemrograman Berorientasi Objek')
        self.assertContains(response, 'Rabu, 13:00-14:30')
        self.assertContains(response, 'Ditolak')

        asisten.refresh_from_db()
        self.assertEqual(get_unread_notification_count(asisten), 0)

    def test_notifikasi_mahasiswa_menampilkan_barang_dipinjam_rusak_dan_hilang(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Reno Pratama',
            nim_nik='2201012',
            email='reno@example.com',
            password='rahasia123',
            no_hp='081111111112',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        status_data = [
            ('Kamera Lapangan', 'dipinjam', 'Dipinjam'),
            ('Tripod Praktikum', 'rusak', 'Rusak'),
            ('Recorder Audio', 'hilang', 'Hilang'),
        ]
        for nama_barang, status, _label in status_data:
            barang = Barang.objects.create(nama=nama_barang, jumlah=1)
            PeminjamanAlat.objects.create(
                barang=barang,
                nama_peminjam='Reno Pratama',
                nim=mahasiswa.nim_nik,
                tanggal_pinjam=date.today(),
                tanggal_kembali=date.today(),
                status=status,
            )
        PeminjamanAlat.objects.create(
            barang=Barang.objects.create(nama='Laptop Lain', jumlah=1),
            nama_peminjam='User Lain',
            nim='2201999',
            tanggal_pinjam=date.today(),
            tanggal_kembali=date.today(),
            status='rusak',
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('kalender:notifikasi_list'))

        for nama_barang, _status, label in status_data:
            self.assertContains(response, f'Status peminjaman {nama_barang}: {label}')
        self.assertNotContains(response, 'Laptop Lain')

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

    def test_notifikasi_aslab_menampilkan_pendaftaran_yang_sudah_digenerate(self):
        aslab = Pengguna.objects.create(
            nama_pengguna='Dina Maharani',
            nim_nik='2201008',
            email='dina-aslab@example.com',
            password='rahasia123',
            no_hp='081111111118',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
        )
        matkul = MataKuliahAsleb.objects.create(
            kode='SDA_GENERATE_TEST',
            nama='Struktur Data',
            dosen='Dosen Test',
            kelas='TIF-01',
        )
        PendaftaranAsleb.objects.create(
            nama='Dina Maharani',
            nim='2201008',
            no_hp='081111111118',
            email='dina-aslab@example.com',
            program_studi='Informatika',
            semester=4,
            matkul=matkul,
            status='digenerate',
        )
        session = self.client.session
        session['pengguna_id'] = aslab.pk
        session.save()

        self.assertGreaterEqual(get_unread_notification_count(aslab), 1)

        response = self.client.get(reverse('kalender:notifikasi_list'))

        self.assertContains(response, 'Pendaftaran aslab Anda masuk Data Aslab')
        self.assertContains(response, 'Struktur Data')
        self.assertContains(response, 'Data Aslab')

        aslab.refresh_from_db()
        self.assertEqual(get_unread_notification_count(aslab), 0)

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


