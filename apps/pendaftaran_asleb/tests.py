from django.test import TestCase
from django.urls import reverse

from apps.asleb.models import Asleb
from apps.pengguna.models import Pengguna

from .models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb
from .utils import get_public_registration_url


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
        self.assertContains(response, 'Pendaftaran Asleb')
        self.assertContains(response, 'Rizki Pratama')
        self.assertContains(response, 'Status: Ditutup')
        self.assertContains(response, 'Buka Pendaftaran')
        self.assertContains(response, get_public_registration_url())

    def test_toggle_pendaftaran_membuka_dan_menutup_form(self):
        response = self.client.post(reverse('pendaftaran_asleb:pendaftaran_toggle_status'))

        self.assertRedirects(response, reverse('pendaftaran_asleb:pendaftaran_list'))
        self.assertTrue(PengaturanPendaftaranAsleb.get_solo().dibuka)

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

        response = self.client.get(reverse('pendaftaran_asleb:pendaftaran_public'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Data mahasiswa otomatis digunakan dari akun Anda.')
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

        post_response = self.client.post(reverse('pendaftaran_asleb:pendaftaran_public'), {
            'semester': 4,
            'matkul': self.matkul.pk,
            'rekening': 'BCA 123456789',
            'alasan': 'Ingin membantu praktikum.',
        })

        self.assertRedirects(post_response, reverse('pendaftaran_asleb:pendaftaran_success'))
        pendaftaran = PendaftaranAsleb.objects.get(nim=mahasiswa.nim_nik)
        self.assertEqual(pendaftaran.nama, mahasiswa.nama_pengguna)
        self.assertEqual(pendaftaran.no_hp, mahasiswa.no_hp)
        self.assertEqual(pendaftaran.email, mahasiswa.email)
        self.assertEqual(pendaftaran.program_studi, mahasiswa.prodi)

    def test_pendaftaran_search_filters_data(self):
        response = self.client.get(reverse('pendaftaran_asleb:pendaftaran_list'), {'q': 'SDA'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rizki Pratama')

    def test_matkul_list_page_loads(self):
        response = self.client.get(reverse('pendaftaran_asleb:matkul_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kelola Matkul Asleb')
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

    def test_generate_semua_diterima_masuk_ke_data_asleb(self):
        self.pendaftaran.status = 'diterima'
        self.pendaftaran.save(update_fields=['status'])

        response = self.client.post(reverse('pendaftaran_asleb:pendaftaran_generate_all_accepted'))

        self.assertEqual(response.status_code, 302)
        self.pendaftaran.refresh_from_db()
        self.assertEqual(self.pendaftaran.status, 'digenerate')
        self.assertTrue(Asleb.objects.filter(nim='2401001', nama='Rizki Pratama').exists())
