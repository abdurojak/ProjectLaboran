import base64

from django.test import TestCase
from django.urls import reverse
from django.core import mail
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.asleb.models import Asleb
from apps.pengguna.models import Pengguna

from .forms import PendaftaranAslebPublicForm
from .models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb
from .utils import get_public_registration_url
from .views import WIZARD_SESSION_KEY


class PendaftaranAslebViewTests(TestCase):
    def setUp(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='Lab Admin',
            nim_nik='ADM-PENDAFTARAN',
            email='admin-pendaftaran@example.com',
            password='rahasia123',
            no_hp='081234567802',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='admin',
        )
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()

        self.matkul = MataKuliahAsleb.objects.get(kode='SDA_TIF01_ABDUL')
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

    def test_public_form_ditutup_jika_pendaftaran_belum_dibuka(self):
        self.client.session.flush()

        response = self.client.get(reverse('pendaftaran_asleb:pendaftaran_public'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pendaftaran sedang ditutup')

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

        transkrip_path = default_storage.save(
            'pendaftaran_asleb/transkrip_tmp/test-transkrip.pdf',
            ContentFile(b'transkrip'),
        )
        session = self.client.session
        session[WIZARD_SESSION_KEY] = {
            'step': 'berkas',
            'matkul_id': self.matkul.pk,
            'transkrip_path': transkrip_path,
            'transkrip_name': 'test-transkrip.pdf',
            'nilai_transkrip': 'A',
            'nilai_lolos': True,
        }
        session.save()

        post_response = self.client.post(reverse('pendaftaran_asleb:pendaftaran_public'), {
            'semester': 4,
            'matkul': self.matkul.pk,
            'cv': SimpleUploadedFile('cv.pdf', b'cv', content_type='application/pdf'),
            'metode_rekening': 'rekening_bank',
            'rekening': 'BCA 123456789',
            'alasan': 'Ingin membantu praktikum.',
            'signature_data': make_signature_data(),
        })

        self.assertRedirects(post_response, reverse('pendaftaran_asleb:pendaftaran_success'))
        pendaftaran = PendaftaranAsleb.objects.get(nim=mahasiswa.nim_nik)
        self.assertEqual(pendaftaran.nama, mahasiswa.nama_pengguna)
        self.assertEqual(pendaftaran.no_hp, mahasiswa.no_hp)
        self.assertEqual(pendaftaran.email, mahasiswa.email)
        self.assertEqual(pendaftaran.program_studi, mahasiswa.prodi)
        self.assertTrue(pendaftaran.tanda_tangan)

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

        self.assertTrue(form.is_valid(), form.errors)
        pendaftaran = form.save()
        self.assertEqual(pendaftaran.nilai_transkrip, 'C')
        self.assertEqual(pendaftaran.skor_nilai, 1)

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

    def test_terima_pendaftaran_mengubah_role_mahasiswa_jadi_asisten_lab(self):
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
        self.assertEqual(pengguna.role, 'asisten_lab')

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
        self.pendaftaran.refresh_from_db()
        pengguna.refresh_from_db()
        self.assertEqual(self.pendaftaran.status, 'digenerate')
        self.assertEqual(pengguna.role, 'asisten_lab')
        self.assertTrue(Asleb.objects.filter(nim='2401001', nama='Rizki Pratama').exists())


def make_signature_data():
    return 'data:image/png;base64,' + base64.b64encode(b'signature-bytes' * 80).decode()
