from django.test import TestCase
from django.urls import reverse

from apps.asleb.models import Asleb
from apps.pengguna.models import Pengguna

from .models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb


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
        self.assertContains(response, 'http://10.24.80.245:8001/pendaftaran-asleb/daftar/')

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
