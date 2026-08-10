import shutil
import tempfile
from datetime import date, time
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.asleb.models import (
    AbsensiAsleb,
    AbsensiMasukAsleb,
    Asleb,
    HonorAsleb,
    ModulPraktikum,
    PengaturanAbsensiAsleb,
)
from apps.asleb.views import sync_honor_from_absensi
from apps.mobile_api.models import MobileSession
from apps.inventaris.models import Barang, FotoInventarisBarang, InventarisBarang, Lokasi
from apps.core.models import PercakapanBantuan, PesanBantuan
from apps.jadwal.models import JadwalPraktikum
from apps.pendaftaran_asleb.models import MataKuliahAsleb, PeriodeAsleb, RiwayatAsleb
from apps.pengguna.models import Pengguna
from apps.peminjaman.models import PeminjamanAlat
from apps.ruangan.models import RuanganLab


def valid_photo(name='selfie.jpg'):
    buffer = BytesIO()
    Image.new('RGB', (80, 80), '#0f766e').save(buffer, format='JPEG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


class MobileAbsensiApiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp(prefix='mobile-absensi-test-')
        cls.media_override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = APIClient()
        self.user = Pengguna.objects.create(
            nama_pengguna='Aslab Mobile', nim_nik='0640020001', email='aslab@std.trisakti.ac.id',
            password='Password123!', no_hp='081200000001', alamat='Jakarta',
            fakultas='Teknologi Industri', prodi='Informatika', gender='laki_laki',
            role='asisten_lab', is_verified=True,
        )
        self.laboran = Pengguna.objects.create(
            nama_pengguna='Laboran Mobile', nim_nik='1000000099', email='laboran.mobile@trisakti.ac.id',
            password='Password123!', no_hp='081200000099', alamat='Jakarta',
            fakultas='Teknologi Industri', prodi='Informatika', gender='laki_laki',
            role='laboran', is_verified=True,
        )
        self.period = PeriodeAsleb.objects.create(
            tahun=2030, semester=1, mulai=date(2030, 1, 1), selesai=date(2030, 6, 30),
            pendaftaran_mulai=date(2030, 1, 1), pendaftaran_selesai=date(2030, 1, 30),
        )
        self.matkul = MataKuliahAsleb.objects.create(
            kode='MOBILE-01', nama='Pemrograman Mobile', dosen='Dosen Mobile', kelas='TIF-01',
        )
        self.asleb = Asleb.objects.create(
            nama=self.user.nama_pengguna, nim=self.user.nim_nik, no_hp=self.user.no_hp,
            email=self.user.email, program_studi=self.user.prodi, semester=5,
            matkul=str(self.matkul), tanggal_bergabung=date.today(), status='aktif',
            periode_aktif=self.period,
        )
        RiwayatAsleb.objects.create(
            nim=self.user.nim_nik, nama=self.user.nama_pengguna, email=self.user.email,
            periode=self.period, matkul=self.matkul, metode_rekening='bni',
            source_pendaftaran_id=90001,
        )
        self.room = RuanganLab.objects.create(kode='LAB-MOBILE', nama='Lab Mobile', kapasitas=30)
        self.schedule = JadwalPraktikum.objects.create(
            mata_kuliah=str(self.matkul), kelas=self.matkul.kelas, ruangan=self.room,
            pengampu=self.matkul.dosen, hari='senin', waktu_mulai=time(8, 0),
            waktu_selesai=time(10, 0), status=JadwalPraktikum.STATUS_DITERIMA,
        )
        PengaturanAbsensiAsleb.objects.update_or_create(pk=1, defaults={'dibuka': True})

    def authenticate(self):
        response = self.client.post(reverse('mobile_api:login'), {
            'identifier': self.user.nim_nik,
            'password': 'Password123!',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['tokens']['access']}")

    def authenticate_laboran(self):
        response = self.client.post(reverse('mobile_api:login'), {
            'identifier': self.laboran.nim_nik,
            'password': 'Password123!',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['user']['role'], 'laboran')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['tokens']['access']}")

    def check_in_payload(self, **overrides):
        payload = {
            'jadwal_id': self.schedule.pk,
            'foto_absensi': valid_photo(),
        }
        payload.update(overrides)
        return payload

    def test_login_menerima_asisten_lab_aktif_dan_laboran(self):
        response = self.client.post(reverse('mobile_api:login'), {
            'identifier': self.user.email,
            'password': 'Password123!',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data['tokens'])

        laboran_response = self.client.post(reverse('mobile_api:login'), {
            'identifier': self.laboran.email,
            'password': 'Password123!',
        }, format='json')
        self.assertEqual(laboran_response.status_code, 200)

        self.user.role = 'mahasiswa'
        self.user.save(update_fields=['role'])
        denied = self.client.post(reverse('mobile_api:login'), {
            'identifier': self.user.email,
            'password': 'Password123!',
        }, format='json')
        self.assertEqual(denied.status_code, 403)

    def test_endpoint_mobile_dipisahkan_berdasarkan_role(self):
        self.authenticate_laboran()
        asleb_endpoint = self.client.get(reverse('mobile_api:schedule_list'))
        self.assertEqual(asleb_endpoint.status_code, 403)

        self.client.credentials()
        self.authenticate()
        laboran_endpoint = self.client.get(reverse('mobile_api:laboran_dashboard'))
        self.assertEqual(laboran_endpoint.status_code, 403)

    @patch('apps.mobile_api.views.bot_answer', return_value='Halo dari LabHub.')
    def test_laboran_dapat_mengakses_endpoint_mobile_bersama(self, bot_answer):
        self.authenticate_laboran()

        profile = self.client.get(reverse('mobile_api:profile'))
        chatbot = self.client.post(
            reverse('mobile_api:chatbot'),
            {'message': 'Halo'},
            format='json',
        )
        logout = self.client.post(reverse('mobile_api:logout'))

        self.assertEqual(profile.status_code, 200, profile.data)
        self.assertEqual(profile.data['user']['role'], 'laboran')
        self.assertIsNone(profile.data['asleb'])
        self.assertEqual(chatbot.status_code, 200, chatbot.data)
        self.assertEqual(chatbot.data['answer'], 'Halo dari LabHub.')
        bot_answer.assert_called_once_with('Halo', self.laboran)
        self.assertEqual(logout.status_code, 204)
        self.assertIsNotNone(MobileSession.objects.get().revoked_at)

    def test_asisten_lab_dapat_meneruskan_chat_ke_admin(self):
        self.authenticate()

        response = self.client.post(
            reverse('mobile_api:chat_admin'),
            {'message': 'Mohon bantu cek absensi saya.'},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'admin')
        conversation = PercakapanBantuan.objects.get(pengguna=self.user)
        self.assertTrue(
            PesanBantuan.objects.filter(
                percakapan=conversation,
                pengirim='pengguna',
                isi='Mohon bantu cek absensi saya.',
            ).exists()
        )

        self.client.credentials()
        self.authenticate_laboran()
        denied = self.client.get(reverse('mobile_api:chat_admin'))
        self.assertEqual(denied.status_code, 403)

    def test_logout_mencabut_access_dan_refresh_token(self):
        login = self.client.post(reverse('mobile_api:login'), {
            'identifier': self.user.email,
            'password': 'Password123!',
        }, format='json')
        access = login.data['tokens']['access']
        refresh = login.data['tokens']['refresh']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        logout = self.client.post(reverse('mobile_api:logout'))

        self.assertEqual(logout.status_code, 204)
        self.assertIsNotNone(MobileSession.objects.get().revoked_at)
        self.assertEqual(self.client.get(reverse('mobile_api:profile')).status_code, 403)
        self.client.credentials()
        refresh_response = self.client.post(
            reverse('mobile_api:refresh'), {'refresh': refresh}, format='json'
        )
        self.assertEqual(refresh_response.status_code, 403)

    def test_refresh_token_hanya_dapat_dipakai_sekali(self):
        login = self.client.post(reverse('mobile_api:login'), {
            'identifier': self.user.email,
            'password': 'Password123!',
        }, format='json')
        refresh = login.data['tokens']['refresh']

        first = self.client.post(
            reverse('mobile_api:refresh'), {'refresh': refresh}, format='json'
        )
        second = self.client.post(
            reverse('mobile_api:refresh'), {'refresh': refresh}, format='json'
        )

        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 403)

    @override_settings(LOGIN_MAX_ATTEMPTS=2, LOGIN_LOCKOUT_SECONDS=60)
    def test_login_dibatasi_setelah_password_salah_berulang(self):
        payload = {'identifier': self.user.email, 'password': 'salah'}

        self.assertEqual(
            self.client.post(reverse('mobile_api:login'), payload, format='json').status_code,
            401,
        )
        self.assertEqual(
            self.client.post(reverse('mobile_api:login'), payload, format='json').status_code,
            401,
        )
        locked = self.client.post(reverse('mobile_api:login'), {
            'identifier': self.user.email,
            'password': 'Password123!',
        }, format='json')

        self.assertEqual(locked.status_code, 429)
        self.assertEqual(locked.data['code'], 'login_locked')

    def test_jadwal_periode_lama_tidak_muncul_di_aplikasi(self):
        old_period = PeriodeAsleb.objects.create(
            tahun=2029, semester=2, mulai=date(2029, 7, 1), selesai=date(2029, 12, 31),
            pendaftaran_mulai=date(2029, 7, 1), pendaftaran_selesai=date(2029, 7, 30),
        )
        old_course = MataKuliahAsleb.objects.create(
            kode='OLD-01', nama='Mata Kuliah Lama', dosen='Dosen Lama', kelas='TIF-99',
        )
        RiwayatAsleb.objects.create(
            nim=self.user.nim_nik, nama=self.user.nama_pengguna, email=self.user.email,
            periode=old_period, matkul=old_course, metode_rekening='bni',
            source_pendaftaran_id=90002,
        )
        old_schedule = JadwalPraktikum.objects.create(
            mata_kuliah=str(old_course), kelas=old_course.kelas, ruangan=self.room,
            pengampu=old_course.dosen, hari='senin', waktu_mulai=time(10, 0),
            waktu_selesai=time(12, 0), status=JadwalPraktikum.STATUS_DITERIMA,
        )
        self.authenticate()

        response = self.client.get(reverse('mobile_api:schedule_list'))

        ids = {item['id'] for item in response.data['results']}
        self.assertIn(self.schedule.pk, ids)
        self.assertNotIn(old_schedule.pk, ids)

    def test_dashboard_laboran_membedakan_total_barang_dan_total_unit(self):
        InventarisBarang.objects.create(nama='Router Mobile', jumlah=3)
        InventarisBarang.objects.create(nama='Kamera Mobile', jumlah=2)
        self.authenticate_laboran()

        response = self.client.get(reverse('mobile_api:laboran_dashboard'))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['summary']['total_barang'], 2)
        self.assertEqual(response.data['summary']['total_unit'], 5)

    def test_laboran_dapat_membuat_inventaris_dengan_beberapa_foto(self):
        location = Lokasi.objects.create(nama_lokasi='Lemari Mobile')
        self.authenticate_laboran()
        response = self.client.post(
            reverse('mobile_api:laboran_inventory'),
            {
                'nama': 'Kamera Praktikum',
                'jumlah': 2,
                'lokasi_id': location.pk,
                'keterangan': 'Perangkat dokumentasi praktikum.',
                'foto': valid_photo('cover.jpg'),
                'foto_galeri': [valid_photo('samping.jpg'), valid_photo('belakang.jpg')],
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 201, response.data)
        inventory = InventarisBarang.objects.get(nama='Kamera Praktikum')
        self.assertEqual(inventory.detail_barang.count(), 2)
        self.assertEqual(FotoInventarisBarang.objects.filter(inventaris=inventory).count(), 2)
        self.assertEqual(len(response.data['foto_urls']), 3)

    def test_upload_gambar_palsu_ditolak_backend(self):
        location = Lokasi.objects.create(nama_lokasi='Lemari Aman')
        self.authenticate_laboran()
        fake_image = SimpleUploadedFile(
            'bukan-gambar.jpg',
            b'<script>alert("xss")</script>',
            content_type='image/jpeg',
        )

        response = self.client.post(
            reverse('mobile_api:laboran_inventory'),
            {
                'nama': 'Barang Tidak Valid',
                'jumlah': 1,
                'lokasi_id': location.pk,
                'foto_galeri': [fake_image],
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(InventarisBarang.objects.filter(nama='Barang Tidak Valid').exists())

    def test_laboran_dapat_melihat_detail_dan_menghapus_inventaris_tanpa_riwayat(self):
        location = Lokasi.objects.create(nama_lokasi='Rak Detail Mobile')
        inventory = InventarisBarang.objects.create(nama='Sensor Mobile', jumlah=1)
        Barang.objects.create(
            inventaris=inventory,
            nama=inventory.nama,
            jumlah=1,
            lokasi=location,
        )
        self.authenticate_laboran()

        detail_url = reverse('mobile_api:laboran_inventory_detail', args=[inventory.pk])
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data['nama'], 'Sensor Mobile')
        self.assertEqual(detail.data['lokasi'][0]['nama'], 'Rak Detail Mobile')

        deleted = self.client.delete(detail_url)
        self.assertEqual(deleted.status_code, 204, deleted.data)
        self.assertFalse(InventarisBarang.objects.filter(pk=inventory.pk).exists())

    def test_laboran_dapat_mengubah_data_dan_menambah_stok_inventaris(self):
        old_location = Lokasi.objects.create(nama_lokasi='Rak Lama Mobile')
        new_location = Lokasi.objects.create(nama_lokasi='Rak Baru Mobile')
        inventory = InventarisBarang.objects.create(
            nama='Sensor Lama',
            jumlah=1,
            keterangan='Keterangan lama',
        )
        Barang.objects.create(
            inventaris=inventory,
            nama=inventory.nama,
            jumlah=1,
            lokasi=old_location,
        )
        self.authenticate_laboran()

        response = self.client.patch(
            reverse('mobile_api:laboran_inventory_detail', args=[inventory.pk]),
            {
                'nama': 'Sensor Baru',
                'jumlah': 3,
                'lokasi_id': new_location.pk,
                'keterangan': 'Keterangan baru',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        inventory.refresh_from_db()
        self.assertEqual(inventory.nama, 'Sensor Baru')
        self.assertEqual(inventory.jumlah, 3)
        self.assertEqual(inventory.keterangan, 'Keterangan baru')
        self.assertEqual(inventory.detail_barang.count(), 3)
        self.assertFalse(
            inventory.detail_barang.exclude(
                nama='Sensor Baru',
                jumlah=3,
                lokasi=new_location,
            ).exists()
        )

    def test_stok_tidak_dapat_dikurangi_jika_unit_memiliki_riwayat(self):
        location = Lokasi.objects.create(nama_lokasi='Rak Aman Mobile')
        inventory = InventarisBarang.objects.create(nama='Router Aman', jumlah=3)
        protected_units = [
            Barang.objects.create(
                inventaris=inventory,
                nama=inventory.nama,
                jumlah=3,
                lokasi=location,
            )
            for _ in range(2)
        ]
        Barang.objects.create(
            inventaris=inventory,
            nama=inventory.nama,
            jumlah=3,
            lokasi=location,
        )
        for index, unit in enumerate(protected_units):
            PeminjamanAlat.objects.create(
                barang=unit,
                nama_peminjam=f'Mahasiswa Lama {index}',
                nim=f'064002008{index}',
                no_hp='0812',
                tanggal_pinjam=date.today(),
                tanggal_kembali=date.today(),
                status='dikembalikan',
            )
        self.authenticate_laboran()

        response = self.client.patch(
            reverse('mobile_api:laboran_inventory_detail', args=[inventory.pk]),
            {
                'nama': inventory.nama,
                'jumlah': 1,
                'lokasi_id': location.pk,
                'keterangan': '',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(
            response.data['code'],
            'inventory_units_have_loan_history',
        )
        self.assertEqual(inventory.detail_barang.count(), 3)

    def test_laboran_tidak_dapat_menghapus_inventaris_dengan_riwayat_peminjaman(self):
        location = Lokasi.objects.create(nama_lokasi='Rak Riwayat Mobile')
        inventory = InventarisBarang.objects.create(nama='Router Riwayat', jumlah=1)
        item = Barang.objects.create(
            inventaris=inventory,
            nama=inventory.nama,
            jumlah=1,
            lokasi=location,
        )
        PeminjamanAlat.objects.create(
            barang=item,
            nama_peminjam='Mahasiswa Lama',
            nim='0640020088',
            no_hp='0812',
            tanggal_pinjam=date.today(),
            tanggal_kembali=date.today(),
            status='dikembalikan',
        )
        self.authenticate_laboran()

        response = self.client.delete(
            reverse('mobile_api:laboran_inventory_detail', args=[inventory.pk])
        )

        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data['code'], 'inventory_has_loan_history')
        self.assertTrue(InventarisBarang.objects.filter(pk=inventory.pk).exists())

    @patch('apps.mobile_api.views.send_peminjaman_status_notification')
    @patch('apps.mobile_api.views.send_peminjaman_status_update')
    def test_laboran_dapat_memproses_peminjaman_dengan_transisi_aman(self, realtime, email):
        location = Lokasi.objects.create(nama_lokasi='Rak Peminjaman')
        inventory = InventarisBarang.objects.create(nama='Router', jumlah=1)
        item = Barang.objects.create(
            inventaris=inventory, nama=inventory.nama, jumlah=1, lokasi=location,
        )
        loan = PeminjamanAlat.objects.create(
            barang=item, nama_peminjam='Mahasiswa', nim='0640020099', no_hp='0812',
            tanggal_pinjam=date.today(), tanggal_kembali=date.today(), status='diajukan',
        )
        self.authenticate_laboran()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('mobile_api:laboran_loan_status', args=[loan.pk]),
                {'status': 'dipinjam'},
                format='json',
            )
        self.assertEqual(response.status_code, 200, response.data)
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'dipinjam')
        email.assert_called_once()
        realtime.assert_called_once()

        invalid = self.client.post(
            reverse('mobile_api:laboran_loan_status', args=[loan.pk]),
            {'status': 'digantikan'},
            format='json',
        )
        self.assertEqual(invalid.status_code, 400)

    def test_daftar_jadwal_hanya_milik_asleb_login(self):
        other_room = RuanganLab.objects.create(kode='LAB-OTHER', nama='Lab Other', kapasitas=20)
        JadwalPraktikum.objects.create(
            mata_kuliah='Matkul Orang Lain', kelas='X', ruangan=other_room, pengampu='Dosen',
            hari='selasa', waktu_mulai=time(8), waktu_selesai=time(9),
            status=JadwalPraktikum.STATUS_DITERIMA,
        )
        self.authenticate()
        response = self.client.get(reverse('mobile_api:schedule_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.schedule.pk)

    @patch('apps.mobile_api.views.validate_schedule_time', return_value=(True, '', 'sudah_absen'))
    def test_absensi_masuk_tanpa_lokasi_menyimpan_foto(self, _mock_time):
        self.authenticate()
        response = self.client.post(
            reverse('mobile_api:check_in'), self.check_in_payload(), format='multipart'
        )
        self.assertEqual(response.status_code, 201, response.data)
        attendance = AbsensiMasukAsleb.objects.get()
        self.assertEqual(attendance.asleb, self.asleb)
        self.assertTrue(attendance.foto_absensi)
        self.assertFalse(attendance.video_absensi)
        self.assertIsNone(attendance.latitude)
        self.assertIsNone(attendance.longitude)
        self.assertTrue(HonorAsleb.objects.filter(asleb=self.asleb, total_pertemuan=1).exists())

        duplicate = self.client.post(
            reverse('mobile_api:check_in'), self.check_in_payload(), format='multipart'
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(AbsensiMasukAsleb.objects.count(), 1)

    @patch('apps.mobile_api.views.validate_schedule_time', return_value=(True, '', 'sudah_absen'))
    def test_absensi_web_dan_mobile_jadwal_yang_sama_tidak_menggandakan_honor(self, _mock_time):
        module = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=1,
            judul='Modul Sinkronisasi',
            file=SimpleUploadedFile(
                'modul-sinkron.pdf',
                b'%PDF-1.4\n%%EOF',
                content_type='application/pdf',
            ),
            diunggah_oleh=self.laboran,
        )
        web_attendance = AbsensiAsleb.objects.create(
            asleb=self.asleb,
            jadwal=self.schedule,
            modul_praktikum=module,
            tanggal_praktikum=timezone.localdate(),
            modul=1,
            file_modul='absensi_asleb/modul/modul-sinkron.pdf',
            bukti_video='absensi_asleb/video/video-sinkron.mp4',
        )
        sync_honor_from_absensi(web_attendance)

        self.authenticate()
        response = self.client.post(
            reverse('mobile_api:check_in'), self.check_in_payload(), format='multipart'
        )

        self.assertEqual(response.status_code, 201, response.data)
        honor = HonorAsleb.objects.get(
            asleb=self.asleb,
            bulan=timezone.localdate().replace(day=1),
        )
        self.assertEqual(honor.total_pertemuan, 1)

    @patch('apps.mobile_api.views.validate_schedule_time', return_value=(True, '', 'sudah_absen'))
    def test_jadwal_orang_lain_tidak_dapat_diabsen(self, _mock_time):
        other_room = RuanganLab.objects.create(kode='LAB-X', nama='Lab X', kapasitas=20)
        other_schedule = JadwalPraktikum.objects.create(
            mata_kuliah='Milik Asleb Lain', kelas='X', ruangan=other_room, pengampu='Dosen',
            hari='senin', waktu_mulai=time(8), waktu_selesai=time(10),
            status=JadwalPraktikum.STATUS_DITERIMA,
        )
        self.authenticate()
        response = self.client.post(
            reverse('mobile_api:check_in'),
            self.check_in_payload(jadwal_id=other_schedule.pk),
            format='multipart',
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AbsensiMasukAsleb.objects.exists())
