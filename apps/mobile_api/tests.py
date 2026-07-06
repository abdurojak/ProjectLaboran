import shutil
import tempfile
from datetime import date, time
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.asleb.models import AbsensiMasukAsleb, Asleb, PengaturanAbsensiAsleb
from apps.jadwal.models import JadwalPraktikum
from apps.pendaftaran_asleb.models import MataKuliahAsleb, PeriodeAsleb, RiwayatAsleb
from apps.pengguna.models import Pengguna
from apps.ruangan.models import RuanganLab


def valid_photo(name='selfie.jpg'):
    buffer = BytesIO()
    Image.new('RGB', (80, 80), '#0f766e').save(buffer, format='JPEG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


@override_settings(
    ABSENSI_CENTER_LATITUDE=0.0,
    ABSENSI_CENTER_LONGITUDE=0.0,
    ABSENSI_RADIUS_METERS=200,
    ABSENSI_MAX_GPS_ACCURACY_METERS=50,
)
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

    def check_in_payload(self, **overrides):
        payload = {
            'jadwal_id': self.schedule.pk,
            'latitude': '0.0000000',
            'longitude': '0.0000000',
            'accuracy': '5.00',
            'foto_absensi': valid_photo(),
        }
        payload.update(overrides)
        return payload

    def test_login_hanya_menerima_asisten_lab_aktif(self):
        response = self.client.post(reverse('mobile_api:login'), {
            'identifier': self.user.email,
            'password': 'Password123!',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data['tokens'])

        self.user.role = 'mahasiswa'
        self.user.save(update_fields=['role'])
        denied = self.client.post(reverse('mobile_api:login'), {
            'identifier': self.user.email,
            'password': 'Password123!',
        }, format='json')
        self.assertEqual(denied.status_code, 403)

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
    def test_absensi_masuk_menyimpan_gps_dan_foto_tanpa_video(self, _mock_time):
        self.authenticate()
        response = self.client.post(
            reverse('mobile_api:check_in'), self.check_in_payload(), format='multipart'
        )
        self.assertEqual(response.status_code, 201, response.data)
        attendance = AbsensiMasukAsleb.objects.get()
        self.assertEqual(attendance.asleb, self.asleb)
        self.assertTrue(attendance.foto_absensi)
        self.assertFalse(attendance.video_absensi)

        duplicate = self.client.post(
            reverse('mobile_api:check_in'), self.check_in_payload(), format='multipart'
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(AbsensiMasukAsleb.objects.count(), 1)

    @patch('apps.mobile_api.views.validate_schedule_time', return_value=(True, '', 'sudah_absen'))
    def test_absensi_di_luar_radius_ditolak_tanpa_menyimpan_data(self, _mock_time):
        self.authenticate()
        response = self.client.post(
            reverse('mobile_api:check_in'),
            self.check_in_payload(latitude='1.0000000', longitude='1.0000000'),
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['attendance_status'], 'ditolak_di_luar_radius')
        self.assertFalse(AbsensiMasukAsleb.objects.exists())

    @patch('apps.mobile_api.views.validate_schedule_time', return_value=(True, '', 'sudah_absen'))
    def test_akurasi_gps_buruk_ditolak(self, _mock_time):
        self.authenticate()
        response = self.client.post(
            reverse('mobile_api:check_in'), self.check_in_payload(accuracy='80'), format='multipart'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'gps_accuracy_too_low')

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
