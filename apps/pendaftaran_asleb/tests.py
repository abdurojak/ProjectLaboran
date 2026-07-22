import base64
import shutil
import tempfile
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core import mail
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.asleb.models import Asleb, HonorAsleb
from apps.jadwal.models import JadwalPraktikum
from apps.pengguna.models import PengalamanPengguna, Pengguna
from apps.ruangan.models import RuanganLab

from .forms import PendaftaranAslebForm, PendaftaranAslebPublicForm, PublicBerkasPendaftaranForm, RekeningPendaftaranForm
from .models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb, PeriodeAsleb, RiwayatAsleb
from .services import get_asleb_experience, is_registration_open, sync_expired_asleb_periods
from .utils import analyze_transcript, extract_grade_from_transcript, get_public_registration_url
from .views import WIZARD_SESSION_KEY


class PendaftaranAslebViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._temp_media_root = tempfile.mkdtemp(prefix='pendaftaran-asleb-test-media-')
        cls._media_override = override_settings(MEDIA_ROOT=cls._temp_media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._temp_media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        PengaturanPendaftaranAsleb.objects.update_or_create(pk=1, defaults={'dibuka': False})
        pengguna = Pengguna.objects.create(
            nama_pengguna='Lab Laboran',
            nim_nik='LAB-PENDAFTARAN',
            email='laboran-pendaftaran@example.com',
            password='rahasia123',
            no_hp='081234567802',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()
        self.laboran = pengguna

        self.matkul, _ = MataKuliahAsleb.objects.get_or_create(
            kode='SDA_TIF01_ABDUL',
            defaults={
                'nama': 'Struktur Data dan Algoritma',
                'dosen': 'Abdul Rois',
                'kelas': 'TIF-01',
            },
        )
        self.pendaftaran = PendaftaranAsleb.objects.create(
            nama='Rizki Pratama',
            nim='2401001',
            no_hp='081234567891',
            email='rizki@example.com',
            program_studi='Rekayasa Perangkat Lunak',
            semester=3,
            matkul=self.matkul,
            alasan='Ingin membantu praktikum.',
        )

    def test_pendaftaran_list_page_loads(self):
        response = self.client.get(reverse('pendaftaran_asleb:pendaftaran_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pendaftaran Aslab')
        self.assertContains(response, 'Rizki Pratama')
        self.assertContains(response, 'Status: Ditutup')
        self.assertContains(response, 'Buka Pendaftaran')
        self.assertContains(response, get_public_registration_url())
        self.assertContains(response, 'registration-admin-cards')
        self.assertContains(response, 'registration-admin-table')
        self.assertContains(response, 'registration-admin-card-actions')
        self.assertContains(response, 'registration-admin-header')
        self.assertContains(response, 'registration-admin-filter')
        self.assertContains(response, 'registration-admin-control-grid')
        self.assertContains(response, '@media (max-width: 1279px), (hover: none) and (pointer: coarse)')
        self.assertContains(response, '@media (min-width: 641px) and (max-width: 1279px)')
        self.assertContains(response, 'border-top: 1px solid rgba(148, 163, 184, 0.16)')
        self.assertContains(response, 'Terima')

    def test_pendaftaran_success_hanya_mengarahkan_ke_dashboard(self):
        response = self.client.get(reverse('pendaftaran_asleb:pendaftaran_success'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('dashboard:home'))
        self.assertContains(response, 'Kembali ke Dashboard')
        self.assertNotContains(response, reverse('pendaftaran_asleb:pendaftaran_public'))
        self.assertNotContains(response, 'Kembali ke Form')

    def test_toggle_pendaftaran_membuka_dan_menutup_form(self):
        Pengguna.objects.create(
            nama_pengguna='Mahasiswa Pendaftar',
            nim_nik='2401999',
            email='mahasiswa@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567899',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
            is_verified=True,
        )

        response = self.client.post(reverse('pendaftaran_asleb:pendaftaran_toggle_status'))

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_list'))
        self.assertTrue(PengaturanPendaftaranAsleb.get_solo().dibuka)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Pendaftaran asisten laboratorium sudah dibuka', mail.outbox[0].body)

        response = self.client.post(reverse('pendaftaran_asleb:pendaftaran_toggle_status'))

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_list'))
        self.assertFalse(PengaturanPendaftaranAsleb.get_solo().dibuka)

    def test_buka_pendaftaran_memulihkan_periode_yang_sudah_diakhiri(self):
        today = timezone.localdate()
        period = PeriodeAsleb.get_for_date(today)
        period.selesai = today - timedelta(days=1)
        period.pendaftaran_mulai = today
        period.pendaftaran_selesai = today - timedelta(days=1)
        period.diakhiri_pada = timezone.now()
        period.diakhiri_oleh = self.laboran
        period.save(update_fields=[
            'selesai', 'pendaftaran_mulai', 'pendaftaran_selesai',
            'diakhiri_pada', 'diakhiri_oleh', 'diperbarui_pada',
        ])
        PengaturanPendaftaranAsleb.objects.filter(pk=1).update(dibuka=True)

        response = self.client.post(reverse('pendaftaran_asleb:pendaftaran_toggle_status'))

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_list'))
        period.refresh_from_db()
        self.assertIsNone(period.diakhiri_pada)
        self.assertGreaterEqual(period.selesai, today)
        self.assertEqual(period.pendaftaran_mulai, today)
        self.assertGreaterEqual(period.pendaftaran_selesai, today)
        self.assertTrue(is_registration_open())

    def test_public_form_ditutup_jika_pendaftaran_belum_dibuka(self):
        self.client.session.flush()

        response = self.client.get(reverse('pendaftaran_asleb:pendaftaran_public'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pendaftaran sedang ditutup')

    def test_public_form_mengarahkan_ke_login_jika_belum_login(self):
        pengaturan = PengaturanPendaftaranAsleb.get_solo()
        pengaturan.dibuka = True
        pengaturan.save(update_fields=['dibuka'])
        self.client.session.flush()

        response = self.client.get(reverse('pendaftaran_asleb:pendaftaran_public'))

        self.assertRedirects(response, reverse('pengguna:login'))

    def test_qr_pendaftaran_dibuat_lokal_oleh_django(self):
        response = self.client.get(reverse('pendaftaran_asleb:registration_qr'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertGreater(len(response.content), 100)

    def test_public_form_mahasiswa_memakai_sidebar_dan_identitas_akun(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Siti Aminah',
            nim_nik='2201002',
            email='siti@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081111111111',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
            is_verified=True,
            foto=SimpleUploadedFile('siti.jpg', b'foto siti', content_type='image/jpeg'),
        )
        PengalamanPengguna.objects.create(
            pengguna=mahasiswa,
            jabatan='Anggota Himpunan',
            organisasi='Universitas Trisakti',
            tanggal_mulai=date(2025, 1, 1),
        )
        pengaturan = PengaturanPendaftaranAsleb.get_solo()
        pengaturan.dibuka = True
        pengaturan.save(update_fields=['dibuka'])
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('pendaftaran_asleb:pendaftaran_public'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Data akun otomatis digunakan untuk pendaftaran Anda.')
        self.assertContains(response, 'Peminjaman Alat')
        self.assertContains(response, 'Jadwal Praktikum')
        self.assertContains(response, 'Ruangan')
        self.assertNotContains(response, f'href="{reverse("inventaris:barang_list")}"')
        self.assertNotContains(response, f'href="{reverse("pendaftaran_asleb:pendaftaran_list")}"')
        self.assertNotContains(response, 'name="nama" type="text"')
        self.assertNotContains(response, 'name="nim" type="text"')
        self.assertNotContains(response, 'name="no_hp" type="text"')
        self.assertNotContains(response, 'name="email" type="email"')
        self.assertNotContains(response, 'name="program_studi" type="text"')
        self.assertContains(response, 'aslab-registration-page')
        self.assertContains(response, 'aslab-registration-steps')
        self.assertContains(response, 'aslab-registration-actions')
        self.assertContains(response, '@media (max-width: 640px)')

        transkrip_path = default_storage.save(
            'pendaftaran_asleb/transkrip_tmp/test-transkrip.pdf',
            ContentFile(b'transkrip'),
        )
        session = self.client.session
        session[WIZARD_SESSION_KEY] = {
            'step': 'berkas',
            'owner_pengguna_id': mahasiswa.pk,
            'matkul_id': self.matkul.pk,
            'transkrip_path': transkrip_path,
            'transkrip_name': 'test-transkrip.pdf',
            'nilai_transkrip': 'A',
            'nilai_lolos': True,
            'nim_terverifikasi': True,
        }
        session.save()

        post_response = self.client.post(reverse('pendaftaran_asleb:pendaftaran_public'), {
            'semester': 4,
            'matkul': self.matkul.pk,
            'metode_rekening': 'bni',
            'rekening': '123456789',
            'nama_pemilik_rekening': 'Mahasiswa Pendaftar',
            'alasan': 'Ingin membantu praktikum.',
            'signature_data': make_signature_data(),
            'pernyataan_data': 'on',
            'pernyataan_kesanggupan': 'on',
        })

        self.assertRedirects(post_response, reverse('pendaftaran_asleb:pendaftaran_success'))
        pendaftaran = PendaftaranAsleb.objects.get(nim=mahasiswa.nim_nik)
        self.assertEqual(pendaftaran.nama, mahasiswa.nama_pengguna)
        self.assertEqual(pendaftaran.no_hp, mahasiswa.no_hp)
        self.assertEqual(pendaftaran.email, mahasiswa.email)
        self.assertEqual(pendaftaran.program_studi, mahasiswa.prodi)
        self.assertTrue(pendaftaran.tanda_tangan)
        self.assertTrue(pendaftaran.cv.name.endswith('.pdf'))

    def test_public_form_langsung_mengarahkan_ke_profil_jika_data_belum_lengkap(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Profil Belum Lengkap',
            nim_nik='2201003',
            email='belum-lengkap@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081111111112',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
            is_verified=True,
        )
        pengaturan = PengaturanPendaftaranAsleb.get_solo()
        pengaturan.dibuka = True
        pengaturan.save(update_fields=['dibuka'])
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('pendaftaran_asleb:pendaftaran_public'))

        self.assertRedirects(response, reverse('pengguna:detail', args=[mahasiswa.pk]))
        self.assertFalse(PendaftaranAsleb.objects.filter(nim=mahasiswa.nim_nik).exists())

    def test_pilih_matkul_ditolak_jika_profil_belum_lengkap(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Tanpa CV',
            nim_nik='0642201099',
            email='tanpacv@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081111111199',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
            is_verified=True,
        )
        pengaturan = PengaturanPendaftaranAsleb.get_solo()
        pengaturan.dibuka = True
        pengaturan.save(update_fields=['dibuka'])
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.post(
            reverse('pendaftaran_asleb:pendaftaran_public'),
            {'matkul': self.matkul.pk},
        )

        self.assertRedirects(response, reverse('pengguna:detail', args=[mahasiswa.pk]))

    def test_transkrip_dengan_nim_akun_dapat_lanjut(self):
        mahasiswa = self.create_mahasiswa_dengan_cv('0642201040')
        self.start_transcript_step(mahasiswa)
        transcript = SimpleUploadedFile(
            'transkrip.txt',
            b'NIM: 0642201040\nStruktur Data dan Algoritma 3 A',
            content_type='text/plain',
        )

        response = self.client.post(
            reverse('pendaftaran_asleb:pendaftaran_public'),
            {'transkrip': transcript},
        )

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_public'))
        wizard = self.client.session[WIZARD_SESSION_KEY]
        self.assertEqual(wizard['step'], 'berkas')
        self.assertTrue(wizard['nim_terverifikasi'])
        self.assertEqual(wizard['nilai_transkrip'], 'A')

    def test_transkrip_dengan_nim_berbeda_tidak_dapat_lanjut(self):
        mahasiswa = self.create_mahasiswa_dengan_cv('0642201041')
        self.start_transcript_step(mahasiswa)
        transcript = SimpleUploadedFile(
            'transkrip.txt',
            b'NIM: 0642209999\nStruktur Data dan Algoritma 3 A',
            content_type='text/plain',
        )

        response = self.client.post(
            reverse('pendaftaran_asleb:pendaftaran_public'),
            {'transkrip': transcript},
        )

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_public'))
        wizard = self.client.session[WIZARD_SESSION_KEY]
        self.assertEqual(wizard['step'], 'transkrip')
        self.assertFalse(wizard['nim_terverifikasi'])
        self.assertFalse(wizard.get('transkrip_path'))

    def test_transkrip_nilai_c_tidak_dapat_lanjut(self):
        mahasiswa = self.create_mahasiswa_dengan_cv('0642201042')
        self.start_transcript_step(mahasiswa)
        transcript = SimpleUploadedFile(
            'transkrip-c.txt',
            b'NIM: 0642201042\nStruktur Data dan Algoritma 3 C',
            content_type='text/plain',
        )

        response = self.client.post(
            reverse('pendaftaran_asleb:pendaftaran_public'),
            {'transkrip': transcript},
        )

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_public'))
        wizard = self.client.session[WIZARD_SESSION_KEY]
        self.assertEqual(wizard['step'], 'transkrip')
        self.assertFalse(wizard['nilai_lolos'])

    def test_bisa_kembali_sebelum_upload_transkrip(self):
        mahasiswa = self.create_mahasiswa_dengan_cv('0642201043')
        self.start_transcript_step(mahasiswa)

        response = self.client.post(
            reverse('pendaftaran_asleb:pendaftaran_public'),
            {'action': 'back'},
        )

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_public'))
        self.assertEqual(self.client.session[WIZARD_SESSION_KEY]['step'], 'matkul')

    def test_tahap_pendaftaran_direset_saat_akun_mahasiswa_berganti(self):
        mahasiswa_a = self.create_mahasiswa_dengan_cv('0642201045')
        transkrip_path = default_storage.save(
            'pendaftaran_asleb/transkrip_tmp/akun-a.pdf',
            ContentFile(b'transkrip akun A'),
        )
        session = self.client.session
        session[WIZARD_SESSION_KEY] = {
            'step': 'transkrip',
            'owner_pengguna_id': mahasiswa_a.pk,
            'matkul_id': self.matkul.pk,
            'transkrip_path': transkrip_path,
        }
        session.save()

        mahasiswa_b = self.create_mahasiswa_dengan_cv('0642201046')
        response = self.client.get(reverse('pendaftaran_asleb:pendaftaran_public'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'matkul')
        wizard = self.client.session[WIZARD_SESSION_KEY]
        self.assertEqual(wizard['owner_pengguna_id'], mahasiswa_b.pk)
        self.assertNotIn('matkul_id', wizard)
        self.assertFalse(default_storage.exists(transkrip_path))

    def test_tahap_berkas_bisa_kembali_tanpa_mengisi_form(self):
        mahasiswa = self.create_mahasiswa_dengan_cv('0642201044')
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session[WIZARD_SESSION_KEY] = {
            'step': 'berkas',
            'owner_pengguna_id': mahasiswa.pk,
            'matkul_id': self.matkul.pk,
            'transkrip_path': 'pendaftaran_asleb/transkrip_tmp/contoh.pdf',
            'nilai_transkrip': 'A',
            'nilai_lolos': True,
            'nim_terverifikasi': True,
        }
        session.save()

        response = self.client.post(
            reverse('pendaftaran_asleb:pendaftaran_public'),
            {'action': 'back'},
        )

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_public'))
        self.assertEqual(self.client.session[WIZARD_SESSION_KEY]['step'], 'transkrip')

    def test_transkrip_pdf_rusak_tetap_dibaca_dengan_fallback_pdfium(self):
        transcript = SimpleUploadedFile(
            'transkrip.pdf',
            b'not-a-valid-pdf-stream',
            content_type='application/pdf',
        )

        text_page = MagicMock()
        text_page.get_text_range.return_value = (
            'NIM: 0642201040\n'
            'Struktur Data dan Algoritma 3 A\n'
        )
        page = MagicMock()
        page.get_textpage.return_value = text_page
        document = MagicMock()
        document.__iter__.return_value = iter([page])

        with patch('pypdf.PdfReader', side_effect=Exception('broken pdf')):
            with patch.dict('sys.modules', {'pypdfium2': SimpleNamespace(PdfDocument=lambda *_args, **_kwargs: document)}):
                grade, nim_matches = analyze_transcript(
                    transcript,
                    self.matkul,
                    expected_nim='0642201040',
                )

        self.assertEqual(grade, 'A')
        self.assertTrue(nim_matches)

    def create_mahasiswa_dengan_cv(self, nim):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna=f'Mahasiswa {nim}',
            nim_nik=nim,
            email=f'{nim}@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081111111188',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
            is_verified=True,
            foto=SimpleUploadedFile(f'foto-{nim}.jpg', b'foto', content_type='image/jpeg'),
        )
        PengalamanPengguna.objects.create(
            pengguna=mahasiswa,
            jabatan='Anggota Organisasi',
            organisasi='Universitas Trisakti',
            tanggal_mulai=date(2025, 1, 1),
        )
        pengaturan = PengaturanPendaftaranAsleb.get_solo()
        pengaturan.dibuka = True
        pengaturan.save(update_fields=['dibuka'])
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()
        return mahasiswa

    def start_transcript_step(self, mahasiswa):
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session[WIZARD_SESSION_KEY] = {
            'step': 'transkrip',
            'owner_pengguna_id': mahasiswa.pk,
            'matkul_id': self.matkul.pk,
        }
        session.save()

    def test_public_form_semester_hanya_tiga_sampai_delapan(self):
        form = PendaftaranAslebPublicForm(data={
            'nama': 'Andi',
            'nim': '2201003',
            'no_hp': '081111111112',
            'email': 'andi@std.trisakti.ac.id',
            'program_studi': 'Informatika',
            'semester': 2,
            'matkul': self.matkul.pk,
            'metode_rekening': 'dana',
            'rekening': '081111111112',
            'signature_data': make_signature_data(),
        })

        self.assertFalse(form.is_valid())
        self.assertIn('semester', form.errors)

    def test_pendaftaran_form_save_assigns_current_periode(self):
        form = PendaftaranAslebForm(data={
            'nama': 'Andi Saputra',
            'nim': '2201010',
            'no_hp': '081111111120',
            'email': 'andi.saputra@std.trisakti.ac.id',
            'program_studi': 'Informatika',
            'semester': 4,
            'matkul': self.matkul.pk,
            'metode_rekening': 'dana',
            'rekening': '081111111120',
            'nama_pemilik_rekening': 'Andi Saputra',
            'nilai_transkrip': 'A',
            'alasan': 'Ingin membantu kegiatan praktikum.',
            'status': 'diajukan',
        })

        self.assertTrue(form.is_valid(), form.errors)
        pendaftaran = form.save()

        self.assertEqual(pendaftaran.periode, PeriodeAsleb.get_for_date(timezone.localdate()))

    def test_public_form_mendeteksi_nilai_transkrip(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Dian Putri',
            nim_nik='2201004',
            email='dian@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081111111113',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
            is_verified=True,
        )
        transcript = SimpleUploadedFile(
            'transkrip-nilai-a.txt',
            b'Mata kuliah Struktur Data dan Algoritma\nNilai: A',
            content_type='text/plain',
        )
        form = PendaftaranAslebPublicForm(
            data={
                'semester': 4,
                'matkul': self.matkul.pk,
                'metode_rekening': 'ovo',
                'rekening': '081111111113',
                'signature_data': make_signature_data(),
            },
            files={'transkrip': transcript},
            current_pengguna=mahasiswa,
        )

        self.assertTrue(form.is_valid(), form.errors)
        pendaftaran = form.save()
        self.assertEqual(pendaftaran.nilai_transkrip, 'A')
        self.assertEqual(pendaftaran.skor_nilai, 3)

    def test_public_form_mendeteksi_nilai_berdasarkan_matkul_dipilih(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Bima Pratama',
            nim_nik='2201006',
            email='bima@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081111111116',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
            is_verified=True,
        )
        transcript = SimpleUploadedFile(
            'transkrip-multi-matkul.txt',
            (
                b'Pemrograman Web 3 A\n'
                b'Struktur Data dan Algoritma 3 C\n'
                b'Jaringan Komputer 3 B\n'
            ),
            content_type='text/plain',
        )
        form = PendaftaranAslebPublicForm(
            data={
                'semester': 4,
                'matkul': self.matkul.pk,
                'metode_rekening': 'ovo',
                'rekening': '081111111116',
                'signature_data': make_signature_data(),
            },
            files={'transkrip': transcript},
            current_pengguna=mahasiswa,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('transkrip', form.errors)

    def test_extract_grade_menormalkan_nilai_plus_minus(self):
        transcript = SimpleUploadedFile(
            'transkrip-plus-minus.txt',
            b'Struktur Data dan Algoritma 3 B+\nMachine Learning 3 C+\n',
            content_type='text/plain',
        )

        detected_grade = extract_grade_from_transcript(transcript, self.matkul)

        self.assertEqual(detected_grade, 'B')

    def test_extract_grade_memakai_kode_mk_transkrip(self):
        matkul = MataKuliahAsleb.objects.create(
            kode='KODE_TRANSKRIP_TEST',
            kode_mk='IKS6404',
            nama='Nama Lokal Tidak Sama',
            sks=4,
            dosen='Dosen Test',
            kelas='TIF-01',
        )
        transcript = SimpleUploadedFile(
            'transkrip-kode-mk.txt',
            (
                b'Pemrograman Berorientasi Objek\n'
                b'Object Oriented Programming\n'
                b'IKS6404 4.00 A 4.00 16.00\n'
            ),
            content_type='text/plain',
        )

        detected_grade = extract_grade_from_transcript(transcript, matkul)

        self.assertEqual(detected_grade, 'A')

    def test_public_form_wajib_tanda_tangan(self):
        form = PendaftaranAslebPublicForm(data={
            'nama': 'Andi',
            'nim': '2201005',
            'no_hp': '081111111114',
            'email': 'andi@std.trisakti.ac.id',
            'program_studi': 'Informatika',
            'semester': 4,
            'matkul': self.matkul.pk,
            'metode_rekening': 'dana',
            'rekening': '081111111114',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('signature_data', form.errors)

    def test_tahap_berkas_wajib_menyetujui_pernyataan_data(self):
        mahasiswa = self.create_mahasiswa_dengan_cv('0642201045')
        form = PublicBerkasPendaftaranForm(
            data={
                'semester': 4,
                'metode_rekening': 'bni',
                'rekening': '1234567890',
                'signature_data': make_signature_data(),
                'pernyataan_kesanggupan': 'on',
            },
            current_pengguna=mahasiswa,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('pernyataan_data', form.errors)
        self.assertIn(
            'Anda wajib memverifikasi dan menyetujui pernyataan data sebelum mengirim pendaftaran.',
            form.errors['pernyataan_data'],
        )

    def test_tahap_berkas_wajib_menyetujui_pernyataan_kesanggupan(self):
        mahasiswa = self.create_mahasiswa_dengan_cv('0642201047')
        form = PublicBerkasPendaftaranForm(
            data={
                'semester': 4,
                'metode_rekening': 'bni',
                'rekening': '1234567890',
                'signature_data': make_signature_data(),
                'pernyataan_data': 'on',
            },
            current_pengguna=mahasiswa,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('pernyataan_kesanggupan', form.errors)
        self.assertIn(
            'Anda wajib menyetujui pernyataan kesanggupan menjalankan tugas asisten laboratorium.',
            form.errors['pernyataan_kesanggupan'],
        )

    def test_tahap_berkas_checkbox_pernyataan_memakai_style_verifikasi_data(self):
        mahasiswa = self.create_mahasiswa_dengan_cv('0642201046')
        self.start_transcript_step(mahasiswa)
        session = self.client.session
        wizard = session[WIZARD_SESSION_KEY]
        wizard.update({
            'step': 'berkas',
            'transkrip_path': 'pendaftaran_asleb/transkrip_tmp/contoh.pdf',
            'nilai_transkrip': 'A',
            'nilai_lolos': True,
            'nim_terverifikasi': True,
        })
        session[WIZARD_SESSION_KEY] = wizard
        session.save()

        response = self.client.get(reverse('pendaftaran_asleb:pendaftaran_public'))

        self.assertContains(response, 'registration-check-card')
        self.assertContains(response, '.registration-check-label')
        self.assertContains(response, '.registration-check-input')
        self.assertContains(response, 'Verifikasi dan Pernyataan Data')
        self.assertContains(response, 'Pernyataan Kesanggupan Tugas')
        self.assertContains(response, 'bersedia menjalankan tugas dan kewajiban sebagai Asisten Laboratorium')
        self.assertContains(response, 'Saya menyatakan bahwa seluruh data, dokumen, informasi rekening, dan tanda tangan yang saya kirimkan adalah benar')
        self.assertContains(response, 'accent-color: #0f766e;')
        self.assertContains(response, 'box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.14) !important;')

    def test_rekening_bni_hanya_angka_dan_bank_lain_menerima_nama_bank(self):
        bni_form = RekeningPendaftaranForm(data={
            'metode_rekening': 'bni', 'rekening': 'BNI 12345', 'nama_pemilik_rekening': 'Rizki Pratama',
        }, instance=self.pendaftaran)
        bank_lain_form = RekeningPendaftaranForm(data={
            'metode_rekening': 'bank_lain', 'rekening': 'BCA 12345', 'nama_pemilik_rekening': 'Rizki Pratama',
        }, instance=self.pendaftaran)

        self.assertFalse(bni_form.is_valid())
        self.assertIn('rekening', bni_form.errors)
        self.assertTrue(bank_lain_form.is_valid(), bank_lain_form.errors)

    def test_mahasiswa_dapat_edit_metode_rekening_milik_sendiri(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Rizki Pratama', nim_nik=self.pendaftaran.nim,
            email='rizki@std.trisakti.ac.id', password='rahasia123', no_hp='081234567891',
            alamat='Jakarta', fakultas='Teknologi Industri', prodi='Informatika',
            gender='laki_laki', role='mahasiswa', is_verified=True,
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.post(reverse('pendaftaran_asleb:rekening_update', args=[self.pendaftaran.pk]), {
            'metode_rekening': 'bank_lain',
            'rekening': 'Mandiri 99887766',
            'nama_pemilik_rekening': 'Rizki Pratama',
        })

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_success'))
        self.pendaftaran.refresh_from_db()
        self.assertEqual(self.pendaftaran.metode_rekening, 'bank_lain')
        self.assertEqual(self.pendaftaran.nama_pemilik_rekening, 'Rizki Pratama')

    def test_laboran_wajib_password_benar_untuk_mengakhiri_periode(self):
        period = PeriodeAsleb.get_for_date(timezone.localdate())

        response = self.client.post(reverse('pendaftaran_asleb:periode_end', args=[period.pk]), {
            'password': 'password-salah',
            'konfirmasi': 'on',
        })

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_list'))
        period.refresh_from_db()
        self.assertIsNone(period.diakhiri_pada)

    def test_laboran_dapat_mengatur_tanggal_masa_tugas_manual(self):
        today = timezone.localdate()
        period = PeriodeAsleb.get_for_date(today)
        start = today - timedelta(days=1)
        end = today + timedelta(days=45)

        response = self.client.post(
            reverse('pendaftaran_asleb:periode_dates_update', args=[period.pk]),
            {'mulai': start.isoformat(), 'selesai': end.isoformat()},
        )

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_list'))
        period.refresh_from_db()
        self.assertEqual(period.mulai, start)
        self.assertEqual(period.selesai, end)

    def test_laboran_dapat_mengakhiri_periode_dan_mereset_jadwal_praktikum_asleb(self):
        period = PeriodeAsleb.get_for_date(timezone.localdate())
        akun_asleb = Pengguna.objects.create(
            nama_pengguna='Aslab Akhir Periode', nim_nik='0640020999',
            email='0640020999@std.trisakti.ac.id', password='rahasia123', no_hp='081299999999',
            alamat='Jakarta', fakultas='Teknologi Industri', prodi='Informatika',
            gender='laki_laki', role='asisten_lab', is_verified=True,
        )
        asleb = Asleb.objects.create(
            nama=akun_asleb.nama_pengguna, nim=akun_asleb.nim_nik, no_hp=akun_asleb.no_hp,
            email=akun_asleb.email, program_studi=akun_asleb.prodi, semester=5,
            matkul=str(self.matkul), periode_aktif=period, tanggal_bergabung=period.mulai,
        )
        room, _ = RuanganLab.objects.get_or_create(
            kode='LAB-PERIODE-TEST', defaults={'nama': 'Lab Periode Test', 'kapasitas': 30}
        )
        jadwal_diajukan = JadwalPraktikum.objects.create(
            mata_kuliah=str(self.matkul), kelas=self.matkul.kelas, ruangan=room,
            pengampu=self.matkul.dosen, hari='senin', waktu_mulai='09:00',
            waktu_selesai='11:00', status=JadwalPraktikum.STATUS_DIAJUKAN,
        )
        jadwal_diterima = JadwalPraktikum.objects.create(
            mata_kuliah=str(self.matkul), kelas=f'{self.matkul.kelas}-B', ruangan=room,
            pengampu=self.matkul.dosen, hari='selasa', waktu_mulai='13:00',
            waktu_selesai='15:00', status=JadwalPraktikum.STATUS_DITERIMA,
        )

        response = self.client.post(reverse('pendaftaran_asleb:periode_end', args=[period.pk]), {
            'password': 'rahasia123',
            'konfirmasi': 'on',
        })

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_list'))
        period.refresh_from_db()
        akun_asleb.refresh_from_db()
        asleb.refresh_from_db()
        self.assertEqual(period.diakhiri_oleh, self.laboran)
        self.assertIsNotNone(period.diakhiri_pada)
        self.assertEqual(akun_asleb.role, 'mahasiswa')
        self.assertEqual(asleb.status, 'nonaktif')
        self.assertFalse(JadwalPraktikum.objects.filter(pk=jadwal_diajukan.pk).exists())
        self.assertFalse(JadwalPraktikum.objects.filter(pk=jadwal_diterima.pk).exists())

    def test_laboran_mengakhiri_periode_menyembunyikan_rekap_honor_aslab_nonaktif(self):
        period = PeriodeAsleb.get_for_date(timezone.localdate())
        akun_asleb = Pengguna.objects.create(
            nama_pengguna='Aslab Honor Periode', nim_nik='0640020888',
            email='0640020888@std.trisakti.ac.id', password='rahasia123', no_hp='081288888888',
            alamat='Jakarta', fakultas='Teknologi Industri', prodi='Informatika',
            gender='laki_laki', role='asisten_lab', is_verified=True,
        )
        asleb = Asleb.objects.create(
            nama=akun_asleb.nama_pengguna, nim=akun_asleb.nim_nik, no_hp=akun_asleb.no_hp,
            email=akun_asleb.email, program_studi=akun_asleb.prodi, semester=5,
            matkul=str(self.matkul), periode_aktif=period, tanggal_bergabung=period.mulai,
        )
        HonorAsleb.objects.create(
            asleb=asleb,
            bulan=timezone.localdate().replace(day=1),
            total_pertemuan=3,
            status='diproses',
            assigned_laboran=self.laboran,
        )

        before_response = self.client.get(reverse('asleb:honor_list'), {
            'bulan': timezone.localdate().replace(day=1).strftime('%Y-%m'),
        })
        self.assertContains(before_response, 'Aslab Honor Periode')

        self.client.post(reverse('pendaftaran_asleb:periode_end', args=[period.pk]), {
            'password': 'rahasia123',
            'konfirmasi': 'on',
        })

        after_response = self.client.get(reverse('asleb:honor_list'), {
            'bulan': timezone.localdate().replace(day=1).strftime('%Y-%m'),
        })
        self.assertNotContains(after_response, 'Aslab Honor Periode')

    def test_laboran_mengakhiri_periode_otomatis_menandai_honor_lama_dibayar(self):
        period = PeriodeAsleb.get_for_date(timezone.localdate())
        akun_asleb = Pengguna.objects.create(
            nama_pengguna='Aslab Arsip Honor', nim_nik='0640020777',
            email='0640020777@std.trisakti.ac.id', password='rahasia123', no_hp='081277777777',
            alamat='Jakarta', fakultas='Teknologi Industri', prodi='Informatika',
            gender='laki_laki', role='asisten_lab', is_verified=True,
        )
        asleb = Asleb.objects.create(
            nama=akun_asleb.nama_pengguna, nim=akun_asleb.nim_nik, no_hp=akun_asleb.no_hp,
            email=akun_asleb.email, program_studi=akun_asleb.prodi, semester=5,
            matkul=str(self.matkul), periode_aktif=period, tanggal_bergabung=period.mulai,
        )
        honor = HonorAsleb.objects.create(
            asleb=asleb,
            bulan=timezone.localdate().replace(day=1),
            total_pertemuan=3,
            status='diproses',
            assigned_laboran=self.laboran,
        )

        self.client.post(reverse('pendaftaran_asleb:periode_end', args=[period.pk]), {
            'password': 'rahasia123',
            'konfirmasi': 'on',
        })

        honor.refresh_from_db()
        self.assertEqual(honor.status, 'dibayar')
        self.assertEqual(honor.tanggal_transfer, timezone.localdate())
        self.assertEqual(honor.pic_transfer, 'Arsip Otomatis Periode')
        self.assertIn('Diarsipkan otomatis saat periode Asisten Lab berakhir.', honor.keterangan)

    def test_admin_tidak_dapat_mengakhiri_periode_asleb(self):
        period = PeriodeAsleb.get_for_date(timezone.localdate())
        admin = Pengguna.objects.create(
            nama_pengguna='Admin Sistem', nim_nik='ADM-PERIODE',
            email='admin-periode@trisakti.ac.id', password='rahasia123', no_hp='081288888888',
            alamat='Jakarta', fakultas='Teknologi Industri', prodi='Informatika',
            gender='laki_laki', role='admin', is_verified=True,
        )
        session = self.client.session
        session['pengguna_id'] = admin.pk
        session.save()

        self.client.post(reverse('pendaftaran_asleb:periode_end', args=[period.pk]), {
            'password': 'rahasia123', 'konfirmasi': 'on',
        })

        period.refresh_from_db()
        self.assertIsNone(period.diakhiri_pada)

    def test_pendaftaran_search_filters_data(self):
        response = self.client.get(reverse('pendaftaran_asleb:pendaftaran_list'), {'q': 'SDA'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rizki Pratama')

    def test_matkul_list_page_loads(self):
        response = self.client.get(reverse('pendaftaran_asleb:matkul_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kelola Matkul Aslab')
        self.assertContains(response, 'Struktur Data dan Algoritma')

    def test_matkul_bisa_ditambahkan(self):
        response = self.client.post(reverse('pendaftaran_asleb:matkul_create'), {
            'kode': 'TEST_MATKUL_TIF01',
            'nama': 'Testing Mata Kuliah',
            'dosen': 'Dosen Penguji',
            'kelas': 'TIF-01',
            'aktif': 'on',
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(MataKuliahAsleb.objects.filter(kode='TEST_MATKUL_TIF01').exists())

    def test_matkul_bisa_dihapus(self):
        matkul = MataKuliahAsleb.objects.create(
            kode='TEST_DELETE_TIF01',
            nama='Matkul Hapus',
            dosen='Dosen Hapus',
            kelas='TIF-01',
        )

        response = self.client.post(reverse('pendaftaran_asleb:matkul_delete', args=[matkul.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(MataKuliahAsleb.objects.filter(pk=matkul.pk).exists())

    def test_terima_pendaftaran_hanya_menandai_diterima(self):
        response = self.client.post(
            reverse('pendaftaran_asleb:pendaftaran_accept', args=[self.pendaftaran.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.pendaftaran.refresh_from_db()
        self.assertEqual(self.pendaftaran.status, 'diterima')
        self.assertFalse(Asleb.objects.filter(nim='2401001').exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Pendaftaran Aslab Diterima', mail.outbox[0].subject)

    def test_tolak_pendaftaran_mengirim_email_status(self):
        response = self.client.post(
            reverse('pendaftaran_asleb:pendaftaran_reject', args=[self.pendaftaran.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.pendaftaran.refresh_from_db()
        self.assertEqual(self.pendaftaran.status, 'ditolak')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Pendaftaran Aslab Ditolak', mail.outbox[0].subject)

    def test_terima_pendaftaran_tidak_langsung_mengubah_role_mahasiswa(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='Rizki Pratama',
            nim_nik='2401001',
            email='rizki@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567891',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Rekayasa Perangkat Lunak',
            gender='laki_laki',
            role='mahasiswa',
            is_verified=True,
        )

        response = self.client.post(
            reverse('pendaftaran_asleb:pendaftaran_accept', args=[self.pendaftaran.pk])
        )

        self.assertEqual(response.status_code, 302)
        pengguna.refresh_from_db()
        self.assertEqual(pengguna.role, 'mahasiswa')
        self.assertFalse(Asleb.objects.filter(nim='2401001').exists())

    def test_generate_semua_diterima_masuk_ke_data_asleb(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='Rizki Pratama',
            nim_nik='2401001',
            email='rizki@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567891',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Rekayasa Perangkat Lunak',
            gender='laki_laki',
            role='mahasiswa',
            is_verified=True,
        )
        self.pendaftaran.status = 'diterima'
        self.pendaftaran.save(update_fields=['status'])

        response = self.client.post(reverse('pendaftaran_asleb:pendaftaran_generate_all_accepted'))

        self.assertEqual(response.status_code, 302)
        pengguna.refresh_from_db()
        self.assertFalse(PendaftaranAsleb.objects.filter(pk=self.pendaftaran.pk).exists())
        self.assertEqual(pengguna.role, 'asisten_lab')
        self.assertTrue(Asleb.objects.filter(nim='2401001', nama='Rizki Pratama').exists())
        self.assertTrue(RiwayatAsleb.objects.filter(
            nim='2401001',
            matkul=self.matkul,
            source_pendaftaran_id=self.pendaftaran.pk,
        ).exists())

    def test_generate_membersihkan_diterima_dan_ditolak_tanpa_memindahkan_yang_ditolak(self):
        self.pendaftaran.status = 'diterima'
        self.pendaftaran.save(update_fields=['status'])
        rejected = PendaftaranAsleb.objects.create(
            nama='Calon Ditolak', nim='2401002', no_hp='081234567892',
            email='ditolak@std.trisakti.ac.id', program_studi='Informatika', semester=4,
            matkul=self.matkul, status='ditolak',
        )

        response = self.client.post(reverse('pendaftaran_asleb:pendaftaran_generate_all_accepted'))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(PendaftaranAsleb.objects.filter(pk__in=[self.pendaftaran.pk, rejected.pk]).exists())
        self.assertTrue(Asleb.objects.filter(nim=self.pendaftaran.nim).exists())
        self.assertFalse(Asleb.objects.filter(nim=rejected.nim).exists())
        self.assertFalse(RiwayatAsleb.objects.filter(nim=rejected.nim).exists())

    def test_generate_tidak_membuat_asleb_duplikat(self):
        self.pendaftaran.status = 'diterima'
        self.pendaftaran.save(update_fields=['status'])
        Asleb.objects.create(
            nama='Nama Lama', nim=self.pendaftaran.nim, no_hp='080000000000',
            email='lama@example.com', program_studi='Informatika', semester=3,
            matkul='Matkul Lama', tanggal_bergabung=timezone.localdate(),
        )

        self.client.post(reverse('pendaftaran_asleb:pendaftaran_generate_all_accepted'))

        self.assertEqual(Asleb.objects.filter(nim=self.pendaftaran.nim).count(), 1)
        self.assertEqual(Asleb.objects.get(nim=self.pendaftaran.nim).nama, self.pendaftaran.nama)

    def test_generate_dibatalkan_jika_masih_ada_status_diajukan(self):
        self.pendaftaran.status = 'diterima'
        self.pendaftaran.save(update_fields=['status'])
        pending = PendaftaranAsleb.objects.create(
            nama='Masih Diseleksi', nim='2401003', no_hp='081234567893',
            email='seleksi@std.trisakti.ac.id', program_studi='Informatika', semester=4,
            matkul=self.matkul, status='diajukan',
        )

        self.client.post(reverse('pendaftaran_asleb:pendaftaran_generate_all_accepted'))

        self.assertEqual(PendaftaranAsleb.objects.filter(pk__in=[self.pendaftaran.pk, pending.pk]).count(), 2)
        self.assertFalse(Asleb.objects.filter(nim=self.pendaftaran.nim).exists())
        self.assertFalse(RiwayatAsleb.objects.filter(nim=self.pendaftaran.nim).exists())

    def test_generate_rollback_jika_pembuatan_data_asleb_gagal(self):
        self.pendaftaran.status = 'diterima'
        self.pendaftaran.save(update_fields=['status'])

        with patch(
            'apps.pendaftaran_asleb.views.create_or_update_asleb_from_pendaftaran',
            side_effect=RuntimeError('simulasi kegagalan'),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('pendaftaran_asleb:pendaftaran_generate_all_accepted'))

        self.assertTrue(PendaftaranAsleb.objects.filter(pk=self.pendaftaran.pk).exists())
        self.assertFalse(Asleb.objects.filter(nim=self.pendaftaran.nim).exists())
        self.assertFalse(RiwayatAsleb.objects.filter(nim=self.pendaftaran.nim).exists())


def make_signature_data():
    return 'data:image/png;base64,' + base64.b64encode(b'signature-bytes' * 80).decode()


class PeriodeAslebTests(TestCase):
    def setUp(self):
        MataKuliahAsleb.objects.get_or_create(
            kode='PERIODE_TEST',
            defaults={'nama': 'Matkul Periode', 'dosen': 'Dosen Test', 'kelas': 'TIF-01'},
        )

    def test_periode_otomatis_dibagi_dua_dalam_setahun(self):
        first = PeriodeAsleb.get_for_date(date(2026, 3, 10))
        second = PeriodeAsleb.get_for_date(date(2026, 9, 10))

        self.assertEqual(first.nama, 'Januari - Juni 2026')
        self.assertEqual(first.selesai, date(2026, 6, 30))
        self.assertEqual(second.nama, 'Juli - Desember 2026')
        self.assertEqual(second.selesai, date(2026, 12, 31))

    def test_role_kembali_mahasiswa_setelah_periode_berakhir_dan_riwayat_tetap_ada(self):
        period = PeriodeAsleb.get_for_date(date(2025, 3, 1))
        matkul = MataKuliahAsleb.objects.first()
        pengguna = Pengguna.objects.create(
            nama_pengguna='Aslab Selesai', nim_nik='0642201777', email='selesai@std.trisakti.ac.id',
            password='rahasia123', no_hp='081200000001', alamat='Jakarta', fakultas='Teknologi Industri',
            prodi='Informatika', gender='laki_laki', role='asisten_lab',
        )
        registration = PendaftaranAsleb.objects.create(
            nama=pengguna.nama_pengguna, nim=pengguna.nim_nik, no_hp=pengguna.no_hp,
            email=pengguna.email, program_studi=pengguna.prodi, semester=4,
            matkul=matkul, periode=period, status='digenerate',
        )
        Asleb.objects.create(
            nama=pengguna.nama_pengguna, nim=pengguna.nim_nik, no_hp=pengguna.no_hp,
            email=pengguna.email, program_studi=pengguna.prodi, semester=4,
            matkul=str(matkul), tanggal_bergabung=period.mulai, periode_aktif=period,
        )

        sync_expired_asleb_periods(date(2025, 7, 1))

        pengguna.refresh_from_db()
        self.assertEqual(pengguna.role, 'mahasiswa')
        self.assertTrue(PendaftaranAsleb.objects.filter(pk=registration.pk).exists())
        self.assertEqual(PengalamanPengguna.objects.filter(pengguna=pengguna, otomatis=True).count(), 1)

    def test_pengalaman_otomatis_asleb_tidak_duplikat_di_bulan_yang_sama(self):
        period = PeriodeAsleb.get_for_date(date(2025, 3, 1))
        matkul = MataKuliahAsleb.objects.first()
        pengguna = Pengguna.objects.create(
            nama_pengguna='Aslab Pengalaman', nim_nik='0642201887', email='pengalaman@std.trisakti.ac.id',
            password='rahasia123', no_hp='081200000003', alamat='Jakarta', fakultas='Teknologi Industri',
            prodi='Informatika', gender='laki_laki', role='asisten_lab',
        )
        Asleb.objects.create(
            nama=pengguna.nama_pengguna, nim=pengguna.nim_nik, no_hp=pengguna.no_hp,
            email=pengguna.email, program_studi=pengguna.prodi, semester=4,
            matkul=str(matkul), tanggal_bergabung=period.mulai, periode_aktif=period,
        )

        sync_expired_asleb_periods(date(2025, 7, 1))
        sync_expired_asleb_periods(date(2025, 7, 1))

        pengalaman = PengalamanPengguna.objects.filter(pengguna=pengguna, otomatis=True)
        self.assertEqual(pengalaman.count(), 1)
        self.assertIn(str(matkul), pengalaman.first().deskripsi)

    def test_batas_matkul_junior_satu_dan_senior_dua(self):
        self.assertEqual(get_asleb_experience('0642201888'), ('junior', 1))
        matkul = MataKuliahAsleb.objects.first()
        for year in [2024, 2025, 2026]:
            period = PeriodeAsleb.get_for_date(date(year, 3, 1))
            PendaftaranAsleb.objects.create(
                nama='Aslab Senior', nim='0642201888', no_hp='081200000002',
                email='senior@std.trisakti.ac.id', program_studi='Informatika', semester=6,
                matkul=matkul, periode=period, status='digenerate',
            )

        self.assertEqual(get_asleb_experience('0642201888'), ('senior', 2))
