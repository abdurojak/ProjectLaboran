from datetime import time
from unittest.mock import patch

from django.contrib.auth.hashers import check_password
from django import forms
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.asleb.models import Asleb
from apps.kalender.models import KegiatanKalender
from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb
from .models import Fakultas, PengalamanPengguna, Pengguna, Prodi


class PenggunaModelTests(TestCase):
    def test_kode_pengguna_dibuat_dari_id(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='Andi Pratama',
            nim_nik='2201001',
            email='andi@example.com',
            password='rahasia123',
            no_hp='081234567890',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='admin',
        )

        self.assertEqual(pengguna.kode_pengguna, f'USR-{pengguna.id:06d}')

    def test_nim_nik_tidak_boleh_sama(self):
        Pengguna.objects.create(
            nama_pengguna='Andi Pratama',
            nim_nik='2201001',
            email='andi@example.com',
            password='rahasia123',
            no_hp='081234567890',
            alamat='Jakarta',
                fakultas='Teknologi Industri',
                prodi='Informatika',
                gender='laki_laki',
                role='mahasiswa',
            )

        with self.assertRaises(IntegrityError):
            Pengguna.objects.create(
                nama_pengguna='Siti Aminah',
                nim_nik='2201001',
                email='siti@example.com',
                password='rahasia123',
                no_hp='081111111111',
                alamat='Jakarta',
                fakultas='Ekonomi',
                prodi='Manajemen',
                gender='perempuan',
                role='mahasiswa',
            )


class PenggunaViewTests(TestCase):
    def setUp(self):
        self.pengguna = Pengguna.objects.create(
            nama_pengguna='Andi Pratama',
            nim_nik='2201001',
            email='andi@example.com',
            password='rahasia123',
            no_hp='081234567890',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='admin',
        )
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()

    def test_list_page_loads(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Maya Mahasiswa',
            nim_nik='2202001',
            email='maya@example.com',
            password='rahasia123',
            no_hp='081111111111',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        laboran = Pengguna.objects.create(
            nama_pengguna='Lala Laboran',
            nim_nik='3302001',
            email='lala@example.com',
            password='rahasia123',
            no_hp='082222222222',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='laboran',
        )
        asisten = Pengguna.objects.create(
            nama_pengguna='Ali Asisten',
            nim_nik='2202002',
            email='ali@example.com',
            password='rahasia123',
            no_hp='083333333333',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='asisten_lab',
        )

        response = self.client.get(reverse('pengguna:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pengguna')
        self.assertNotContains(response, self.pengguna.kode_pengguna)
        self.assertContains(response, 'Mahasiswa')
        self.assertContains(response, 'Laboran')
        self.assertContains(response, 'Asisten Lab')
        self.assertContains(response, mahasiswa.nama_pengguna)
        self.assertContains(response, laboran.nama_pengguna)
        self.assertContains(response, asisten.nama_pengguna)
        self.assertContains(response, 'data-confirmation-modal')

    def test_laboran_hanya_melihat_mahasiswa_dan_asisten_lab_di_menu_pengguna(self):
        laboran = Pengguna.objects.create(
            nama_pengguna='Lala Laboran',
            nim_nik='3302001',
            email='lala@example.com',
            password='rahasia123',
            no_hp='082222222222',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='laboran',
        )
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Maya Mahasiswa',
            nim_nik='2202001',
            email='maya@example.com',
            password='rahasia123',
            no_hp='081111111111',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        asisten = Pengguna.objects.create(
            nama_pengguna='Ali Asisten',
            nim_nik='2202002',
            email='ali@example.com',
            password='rahasia123',
            no_hp='083333333333',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='asisten_lab',
        )
        session = self.client.session
        session['pengguna_id'] = laboran.pk
        session.save()

        response = self.client.get(reverse('pengguna:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, mahasiswa.nama_pengguna)
        self.assertContains(response, asisten.nama_pengguna)
        self.assertNotContains(response, laboran.kode_pengguna)
        self.assertNotContains(response, '<h3 class="text-xl font-black text-slate-900">Laboran</h3>', html=False)
        self.assertNotContains(response, 'Tambah Pengguna')

    def test_laboran_tidak_bisa_mengelola_pengguna_via_url_langsung(self):
        laboran = Pengguna.objects.create(
            nama_pengguna='Lala Laboran',
            nim_nik='3302001',
            email='lala@example.com',
            password='rahasia123',
            no_hp='082222222222',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='laboran',
        )
        target = Pengguna.objects.create(
            nama_pengguna='Maya Mahasiswa',
            nim_nik='2202001',
            email='maya@example.com',
            password='rahasia123',
            no_hp='081111111111',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='mahasiswa',
        )
        session = self.client.session
        session['pengguna_id'] = laboran.pk
        session.save()

        self.assertRedirects(self.client.get(reverse('pengguna:create')), reverse('pengguna:list'))
        self.assertRedirects(self.client.get(reverse('pengguna:update', args=[target.pk])), reverse('pengguna:list'))
        self.assertRedirects(self.client.post(reverse('pengguna:delete', args=[target.pk])), reverse('pengguna:list'))
        self.assertTrue(Pengguna.objects.filter(pk=target.pk).exists())

    @patch('apps.pengguna.forms.validate_human_face_photo')
    def test_create_pengguna_menyimpan_password_hash_dan_foto(self, mock_validate_face):
        foto = SimpleUploadedFile(
            'andi.gif',
            b'GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;',
            content_type='image/gif',
        )
        response = self.client.post(
            reverse('pengguna:create'),
            {
                'foto': foto,
                'nama_pengguna': 'Budi Santoso',
                'nim_nik': '2201002',
                'email': 'budi@example.com',
                'password': 'passwordku123',
                'no_hp': '081222222222',
                'alamat': 'Depok',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Sistem Informasi',
                'gender': 'laki_laki',
                'role': 'asisten_lab',
            },
        )

        pengguna = Pengguna.objects.get(nim_nik='2201002')
        self.assertRedirects(response, reverse('pengguna:list'), fetch_redirect_response=False)
        self.assertNotEqual(pengguna.password, 'passwordku123')
        self.assertTrue(check_password('passwordku123', pengguna.password))
        self.assertTrue(pengguna.foto)
        self.assertEqual(pengguna.role, 'asisten_lab')

    def test_update_pengguna_tanpa_password_tidak_mengubah_password(self):
        password_lama = self.pengguna.password
        response = self.client.post(
            reverse('pengguna:update', args=[self.pengguna.pk]),
            {
                'nama_pengguna': 'Andi Updated',
                'nim_nik': '2201001',
                'email': 'andi.updated@example.com',
                'password': '',
                'no_hp': '081234567890',
                'alamat': 'Jakarta',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Informatika',
                'gender': 'laki_laki',
                'role': 'laboran',
            },
        )

        self.pengguna.refresh_from_db()
        self.assertRedirects(response, reverse('pengguna:list'))
        self.assertEqual(self.pengguna.nama_pengguna, 'Andi Updated')
        self.assertEqual(self.pengguna.password, password_lama)
        self.assertEqual(self.pengguna.role, 'laboran')

    def test_detail_pengguna_tidak_menampilkan_tombol_hapus(self):
        response = self.client.get(reverse('pengguna:detail', args=[self.pengguna.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Profil')
        self.assertContains(response, 'Ganti Password')
        self.assertNotContains(response, 'Konfirmasi Hapus Pengguna')
        self.assertNotContains(response, f'href="{reverse("pengguna:delete", args=[self.pengguna.pk])}"')

    def test_detail_asisten_lab_menampilkan_status_junior_senior(self):
        self.pengguna.role = 'asisten_lab'
        self.pengguna.save(update_fields=['role'])
        asleb = Asleb.objects.create(
            nama=self.pengguna.nama_pengguna,
            nim=self.pengguna.nim_nik,
            no_hp=self.pengguna.no_hp,
            email=self.pengguna.email,
            program_studi='Informatika',
            matkul='Pemrograman Web',
            semester=5,
            tanggal_bergabung=timezone.localdate(),
        )

        response = self.client.get(reverse('pengguna:detail', args=[self.pengguna.pk]))

        self.assertContains(response, 'Status Aslab')
        self.assertContains(response, 'Junior')
        self.assertContains(response, '1 periode sebagai aslab.')

        matkul = MataKuliahAsleb.objects.first()
        for index in range(3):
            PendaftaranAsleb.objects.create(
                nama=f'Riwayat {index + 1}',
                nim=asleb.nim,
                no_hp='081234567890',
                email=f'riwayat{index + 1}@std.trisakti.ac.id',
                program_studi='Informatika',
                semester=5,
                matkul=matkul,
                status='digenerate',
            )

        response = self.client.get(reverse('pengguna:detail', args=[self.pengguna.pk]))

        self.assertContains(response, 'Senior')
        self.assertContains(response, '3 periode sebagai aslab.')

    def test_update_profile_mengubah_data_pengguna(self):
        response = self.client.post(
            reverse('pengguna:update_profile', args=[self.pengguna.pk]),
            {
                'nama_pengguna': 'Andi Profil Baru',
                'nim_nik': '2201001',
                'email': 'andi.profil@example.com',
                'gender': 'laki_laki',
                'no_hp': '081234567890',
                'alamat': 'Bekasi',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Sistem Informasi',
                'role': 'laboran',
                'hapus_foto': '0',
            },
        )

        self.pengguna.refresh_from_db()
        self.assertRedirects(response, reverse('pengguna:detail', args=[self.pengguna.pk]))
        self.assertEqual(self.pengguna.nama_pengguna, 'Andi Profil Baru')
        self.assertEqual(self.pengguna.email, 'andi.profil@example.com')
        self.assertEqual(self.pengguna.no_hp, '081234567890')
        self.assertEqual(self.pengguna.role, 'laboran')

    def test_update_profile_no_hp_baru_langsung_disimpan_tanpa_otp(self):
        response = self.client.post(
            reverse('pengguna:update_profile', args=[self.pengguna.pk]),
            {
                'nama_pengguna': 'Andi Profil Baru',
                'nim_nik': '2201001',
                'email': 'andi.profil@example.com',
                'gender': 'laki_laki',
                'no_hp': '089999999999',
                'alamat': 'Bekasi',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Sistem Informasi',
                'role': 'laboran',
                'hapus_foto': '0',
            },
        )

        self.pengguna.refresh_from_db()
        self.assertRedirects(response, reverse('pengguna:detail', args=[self.pengguna.pk]))
        self.assertEqual(self.pengguna.nama_pengguna, 'Andi Profil Baru')
        self.assertEqual(self.pengguna.email, 'andi.profil@example.com')
        self.assertEqual(self.pengguna.no_hp, '089999999999')
        self.assertNotIn('pengguna_otp', self.client.session)

    def test_update_profile_no_hp_menolak_huruf(self):
        response = self.client.post(
            reverse('pengguna:update_profile', args=[self.pengguna.pk]),
            {
                'nama_pengguna': 'Andi Profil Baru',
                'nim_nik': '2201001',
                'email': 'andi.profil@example.com',
                'gender': 'laki_laki',
                'no_hp': '08ABC',
                'alamat': 'Bekasi',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Sistem Informasi',
                'role': 'laboran',
                'hapus_foto': '0',
            },
        )

        self.pengguna.refresh_from_db()
        self.assertRedirects(response, reverse('pengguna:detail', args=[self.pengguna.pk]))
        self.assertEqual(self.pengguna.no_hp, '081234567890')
        self.assertNotIn('pengguna_otp', self.client.session)

    @patch('apps.pengguna.forms.validate_human_face_photo')
    def test_update_profile_menolak_foto_tanpa_wajah(self, mock_validate_face):
        mock_validate_face.side_effect = forms.ValidationError('Foto harus menampilkan wajah manusia yang jelas.')
        foto = SimpleUploadedFile('pemandangan.jpg', b'not a face', content_type='image/jpeg')

        response = self.client.post(
            reverse('pengguna:update_profile', args=[self.pengguna.pk]),
            {
                'foto': foto,
                'nama_pengguna': 'Andi Profil Baru',
                'nim_nik': '2201001',
                'email': 'andi.profil@example.com',
                'gender': 'laki_laki',
                'no_hp': '089999999999',
                'alamat': 'Bekasi',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Sistem Informasi',
                'role': 'laboran',
                'hapus_foto': '0',
            },
        )

        self.assertRedirects(response, reverse('pengguna:detail', args=[self.pengguna.pk]))
        self.pengguna.refresh_from_db()
        self.assertFalse(self.pengguna.foto)

    def test_mahasiswa_tidak_bisa_mengubah_role_lewat_update_profile(self):
        self.pengguna.role = 'mahasiswa'
        self.pengguna.save(update_fields=['role'])
        response = self.client.post(
            reverse('pengguna:update_profile', args=[self.pengguna.pk]),
            {
                'nama_pengguna': 'Andi Mahasiswa',
                'nim_nik': '2201001',
                'email': 'andi.mahasiswa@example.com',
                'gender': 'laki_laki',
                'no_hp': '081234567890',
                'alamat': 'Jakarta',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Informatika',
                'role': 'admin',
                'hapus_foto': '0',
            },
        )

        self.pengguna.refresh_from_db()
        self.assertRedirects(response, reverse('pengguna:detail', args=[self.pengguna.pk]))
        self.assertEqual(self.pengguna.nama_pengguna, 'Andi Mahasiswa')
        self.assertEqual(self.pengguna.role, 'mahasiswa')

    def test_change_password_mengganti_password_pengguna(self):
        response = self.client.post(
            reverse('pengguna:change_password', args=[self.pengguna.pk]),
            {
                'password': 'passwordbaru123',
                'password_confirmation': 'passwordbaru123',
            },
        )

        self.pengguna.refresh_from_db()
        self.assertRedirects(response, reverse('pengguna:detail', args=[self.pengguna.pk]))
        self.assertTrue(check_password('passwordbaru123', self.pengguna.password))

    def test_change_password_menolak_konfirmasi_tidak_sama(self):
        password_lama = self.pengguna.password
        response = self.client.post(
            reverse('pengguna:change_password', args=[self.pengguna.pk]),
            {
                'password': 'passwordbaru123',
                'password_confirmation': 'berbeda123',
            },
        )

        self.pengguna.refresh_from_db()
        self.assertRedirects(response, reverse('pengguna:detail', args=[self.pengguna.pk]))
        self.assertEqual(self.pengguna.password, password_lama)

    def test_delete_pengguna(self):
        response = self.client.post(reverse('pengguna:delete', args=[self.pengguna.pk]))

        self.assertRedirects(response, reverse('pengguna:list'), fetch_redirect_response=False)
        self.assertFalse(Pengguna.objects.filter(pk=self.pengguna.pk).exists())


class PenggunaAuthTests(TestCase):
    def setUp(self):
        self.pengguna = Pengguna.objects.create(
            nama_pengguna='Andi Pratama',
            nim_nik='2201001',
            email='andi@example.com',
            password='rahasia123',
            no_hp='081234567890',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )

    def test_login_menggunakan_nim_nik_dan_password(self):
        response = self.client.post(
            reverse('pengguna:login'),
            {
                'jenis_login': 'mahasiswa',
                'nim_nik': '2201001',
                'password': 'rahasia123',
            },
        )

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(self.client.session['pengguna_id'], self.pengguna.pk)

    def test_login_menolak_next_url_domain_luar(self):
        response = self.client.post(
            f"{reverse('pengguna:login')}?next=https://evil.example/phish",
            {
                'jenis_login': 'mahasiswa',
                'nim_nik': '2201001',
                'password': 'rahasia123',
            },
        )

        self.assertRedirects(response, reverse('dashboard:home'), fetch_redirect_response=False)

    def test_login_menolak_password_salah(self):
        response = self.client.post(
            reverse('pengguna:login'),
            {
                'jenis_login': 'mahasiswa',
                'nim_nik': '2201001',
                'password': 'salah',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NIM/NIK atau password tidak sesuai.')
        self.assertNotIn('pengguna_id', self.client.session)

    def test_login_nim_belum_terdaftar_tidak_membuat_pengguna_baru(self):
        jumlah_awal = Pengguna.objects.count()

        response = self.client.post(
            reverse('pengguna:login'),
            {
                'jenis_login': 'mahasiswa',
                'nim_nik': '9999999',
                'password': 'passwordasal',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NIM/NIK atau password tidak sesuai.')
        self.assertEqual(Pengguna.objects.count(), jumlah_awal)
        self.assertFalse(Pengguna.objects.filter(nim_nik='9999999').exists())
        self.assertNotIn('pengguna_id', self.client.session)

    def test_login_nim_berhuruf_ditolak(self):
        response = self.client.post(
            reverse('pengguna:login'),
            {
                'jenis_login': 'mahasiswa',
                'nim_nik': 'ABC123',
                'password': 'passwordasal',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NIM/NIK hanya boleh berisi angka.')
        self.assertNotIn('pengguna_id', self.client.session)

    def test_login_menolak_akun_belum_terverifikasi(self):
        self.pengguna.is_verified = False
        self.pengguna.save(update_fields=['is_verified'])

        response = self.client.post(
            reverse('pengguna:login'),
            {
                'jenis_login': 'mahasiswa',
                'nim_nik': '2201001',
                'password': 'rahasia123',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Akun belum diverifikasi')
        self.assertNotIn('pengguna_id', self.client.session)

    def test_login_karyawan_hanya_untuk_admin_dan_laboran(self):
        admin = Pengguna.objects.create(
            nama_pengguna='Admin Lab',
            nim_nik='3301001',
            email='admin@example.com',
            password='rahasia123',
            no_hp='081111111111',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='admin',
        )

        response = self.client.post(
            reverse('pengguna:login'),
            {
                'jenis_login': 'karyawan',
                'nim_nik': admin.nim_nik,
                'password': 'rahasia123',
            },
        )

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(self.client.session['pengguna_id'], admin.pk)

    def test_login_mahasiswa_ditolak_di_mode_karyawan(self):
        response = self.client.post(
            reverse('pengguna:login'),
            {
                'jenis_login': 'karyawan',
                'nim_nik': self.pengguna.nim_nik,
                'password': 'rahasia123',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Akun ini bukan akun karyawan')
        self.assertNotIn('pengguna_id', self.client.session)

    def test_register_fakultas_dan_prodi_berupa_dropdown(self):
        response = self.client.get(reverse('pengguna:register'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="nama_pengguna"', html=False)
        self.assertContains(response, 'name="nim_nik"', html=False)
        self.assertContains(response, 'minlength="10"', html=False)
        self.assertContains(response, '<select name="fakultas"', html=False)
        self.assertContains(response, '<select name="prodi"', html=False)
        self.assertContains(response, 'Teknologi Industri')
        self.assertContains(response, 'Informatika')

    def test_halaman_publik_login_register_tidak_menampilkan_sidebar_dashboard(self):
        for url in [reverse('pengguna:login'), reverse('pengguna:register')]:
            response = self.client.get(url)

            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'id="dashboard-sidebar"', html=False)

    def test_login_dan_register_membaca_tema_terakhir_dari_browser(self):
        for url in [reverse('pengguna:login'), reverse('pengguna:register')]:
            response = self.client.get(url)

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "localStorage.getItem(storageKeys.theme)", html=False)
            self.assertContains(response, "localStorage.getItem(storageKeys.background)", html=False)
            self.assertContains(response, "labhub-custom-background", html=False)

    def test_register_dropdown_fakultas_prodi_mengambil_data_database(self):
        Fakultas.objects.create(nama='Fakultas Baru')
        Prodi.objects.create(nama='Prodi Baru')

        response = self.client.get(reverse('pengguna:register'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fakultas Baru')
        self.assertContains(response, 'Prodi Baru')

    def test_register_membuat_pengguna_lalu_verifikasi_otp(self):
        response = self.client.post(
            reverse('pengguna:register'),
            {
                'nama_pengguna': 'Siti Aminah',
                'nim_nik': '0642201002',
                'email': 'siti@std.trisakti.ac.id',
                'password': 'passwordku123',
                'password_confirmation': 'passwordku123',
                'alamat': 'Jakarta',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Informatika',
                'gender': 'perempuan',
            },
            follow=True,
        )

        pengguna = Pengguna.objects.get(nim_nik='0642201002')
        self.assertRedirects(response, reverse('pengguna:verify_register'))
        self.assertEqual(pengguna.nama_pengguna, 'Siti Aminah')
        self.assertTrue(check_password('passwordku123', pengguna.password))
        self.assertEqual(pengguna.role, 'mahasiswa')
        self.assertEqual(pengguna.no_hp, '')
        self.assertFalse(pengguna.is_verified)
        self.assertNotIn('pengguna_id', self.client.session)
        kode = self.client.session['pengguna_otp']['code']
        self.assertContains(response, f'{settings.PUBLIC_ACCESS_BASE_URL}/pengguna/register/verifikasi/?kode={kode}')

        response = self.client.post(reverse('pengguna:verify_register'), {'kode': kode})
        pengguna.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertTrue(pengguna.is_verified)
        self.assertEqual(self.client.session['pengguna_id'], pengguna.pk)

    def test_register_link_verifikasi_langsung_mengaktifkan_akun(self):
        response = self.client.post(
            reverse('pengguna:register'),
            {
                'nama_pengguna': 'Link Verifikasi',
                'nim_nik': '0642201008',
                'email': 'link@std.trisakti.ac.id',
                'password': 'passwordku123',
                'password_confirmation': 'passwordku123',
                'alamat': 'Jakarta',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Informatika',
                'gender': 'laki_laki',
            },
        )

        pengguna = Pengguna.objects.get(nim_nik='0642201008')
        kode = self.client.session['pengguna_otp']['code']

        self.assertRedirects(response, reverse('pengguna:verify_register'))
        self.assertFalse(pengguna.is_verified)

        response = self.client.get(reverse('pengguna:verify_register'), {'kode': kode})
        pengguna.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertTrue(pengguna.is_verified)
        self.assertEqual(self.client.session['pengguna_id'], pengguna.pk)
        self.assertNotIn('pengguna_otp', self.client.session)

    def test_register_menolak_email_domain_trisakti_tanpa_std(self):
        response = self.client.post(
            reverse('pengguna:register'),
            {
                'nama_pengguna': 'Dina Pratama',
                'nim_nik': '0642201003',
                'email': 'dina@trisakti.ac.id',
                'password': 'passwordku123',
                'password_confirmation': 'passwordku123',
                'alamat': 'Jakarta',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Informatika',
                'gender': 'perempuan',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email harus menggunakan domain @std.trisakti.ac.id.')
        self.assertFalse(Pengguna.objects.filter(nim_nik='0642201003').exists())

    def test_register_menolak_password_lemah(self):
        response = self.client.post(
            reverse('pengguna:register'),
            {
                'nama_pengguna': 'Password Lemah',
                'nim_nik': '0642201009',
                'email': 'lemah@std.trisakti.ac.id',
                'password': '123',
                'password_confirmation': '123',
                'alamat': 'Jakarta',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Informatika',
                'gender': 'laki_laki',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Pengguna.objects.filter(nim_nik='0642201009').exists())

    def test_register_menolak_email_non_trisakti(self):
        response = self.client.post(
            reverse('pengguna:register'),
            {
                'nama_pengguna': 'Siti Aminah',
                'nim_nik': '0642201002',
                'email': 'siti@gmail.com',
                'password': 'passwordku123',
                'password_confirmation': 'passwordku123',
                'alamat': 'Jakarta',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Informatika',
                'gender': 'perempuan',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email harus menggunakan domain @std.trisakti.ac.id.')
        self.assertFalse(Pengguna.objects.filter(nim_nik='0642201002').exists())

    def test_register_menolak_email_yang_sudah_terdaftar(self):
        Pengguna.objects.create(
            nama_pengguna='Pemilik Email',
            nim_nik='2201999',
            email='sama@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081111111111',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )

        response = self.client.post(
            reverse('pengguna:register'),
            {
                'nama_pengguna': 'Email Sama',
                'nim_nik': '0642201010',
                'email': 'SAMA@std.trisakti.ac.id',
                'password': 'passwordku123',
                'password_confirmation': 'passwordku123',
                'alamat': 'Jakarta',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Informatika',
                'gender': 'laki_laki',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email sudah terdaftar')
        self.assertFalse(Pengguna.objects.filter(nim_nik='0642201010').exists())

    def test_register_menolak_nim_berhuruf(self):
        response = self.client.post(
            reverse('pengguna:register'),
            {
                'nama_pengguna': 'Siti Aminah',
                'nim_nik': '2201ABC',
                'email': 'siti@std.trisakti.ac.id',
                'password': 'passwordku123',
                'password_confirmation': 'passwordku123',
                'alamat': 'Jakarta',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Informatika',
                'gender': 'perempuan',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NIM hanya boleh berisi angka.')

    def test_register_menolak_nim_kurang_dari_10_digit(self):
        response = self.client.post(
            reverse('pengguna:register'),
            {
                'nama_pengguna': 'NIM Pendek',
                'nim_nik': '123456789',
                'email': 'nimpendek@std.trisakti.ac.id',
                'password': 'passwordku123',
                'password_confirmation': 'passwordku123',
                'alamat': 'Jakarta',
                'fakultas': 'Teknologi Industri',
                'prodi': 'Informatika',
                'gender': 'perempuan',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NIM harus terdiri dari minimal 10 digit.')
        self.assertFalse(Pengguna.objects.filter(nim_nik='123456789').exists())

    def test_forgot_password_mengganti_password_dengan_otp(self):
        response = self.client.post(
            reverse('pengguna:forgot_password'),
            {'nim_nik': '2201001'},
        )

        self.assertRedirects(response, reverse('pengguna:reset_password'))
        kode = self.client.session['pengguna_otp']['code']
        response = self.client.post(reverse('pengguna:reset_password'), {
            'kode': kode,
            'password': 'passwordbaru123',
            'password_confirmation': 'passwordbaru123',
        })
        self.pengguna.refresh_from_db()

        self.assertRedirects(response, reverse('pengguna:login'))
        self.assertTrue(check_password('passwordbaru123', self.pengguna.password))

    def test_reset_password_menolak_password_lama(self):
        response = self.client.post(
            reverse('pengguna:forgot_password'),
            {'nim_nik': '2201001'},
        )

        self.assertRedirects(response, reverse('pengguna:reset_password'))
        kode = self.client.session['pengguna_otp']['code']
        response = self.client.post(reverse('pengguna:reset_password'), {
            'kode': kode,
            'password': 'rahasia123',
            'password_confirmation': 'rahasia123',
        })
        self.pengguna.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Password baru tidak boleh sama dengan password yang sedang digunakan.')
        self.assertTrue(check_password('rahasia123', self.pengguna.password))

    def test_logout_menghapus_session_pengguna(self):
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()

        response = self.client.post(reverse('pengguna:logout'))

        self.assertRedirects(response, reverse('pengguna:login'))
        self.assertNotIn('pengguna_id', self.client.session)

    def test_menu_membutuhkan_login(self):
        response = self.client.get(reverse('dashboard:home'))

        self.assertRedirects(response, f"{reverse('pengguna:login')}?next={reverse('dashboard:home')}")

    def test_menu_bisa_diakses_setelah_login(self):
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.status_code, 200)

    def test_mahasiswa_hanya_bisa_membuka_menu_tertentu(self):
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()

        allowed_response = self.client.get(reverse('peminjaman:peminjaman_list'))
        kalender_response = self.client.get(reverse('kalender:kegiatan_list'))
        ruangan_response = self.client.get(reverse('ruangan:ruangan_list'))
        blocked_response = self.client.get(reverse('inventaris:barang_list'))

        self.assertEqual(allowed_response.status_code, 200)
        self.assertEqual(kalender_response.status_code, 200)
        self.assertEqual(ruangan_response.status_code, 200)
        self.assertContains(allowed_response, 'Dashboard')
        self.assertContains(allowed_response, 'Kalender')
        self.assertContains(allowed_response, 'Peminjaman Alat')
        self.assertContains(allowed_response, 'Jadwal Praktikum')
        self.assertContains(allowed_response, 'Ruangan')
        self.assertContains(kalender_response, 'Kalender Kegiatan')
        self.assertContains(ruangan_response, 'Daftar Lab')
        self.assertNotContains(allowed_response, 'Inventaris')
        self.assertNotContains(allowed_response, 'Pengguna')
        self.assertRedirects(blocked_response, reverse('dashboard:home'))

    def test_mahasiswa_bisa_membuat_kegiatan_pribadi_tapi_tidak_mengelola_kegiatan_lain(self):
        kegiatan = KegiatanKalender.objects.create(
            judul='Workshop IoT',
            tanggal=timezone.localdate(),
            waktu_mulai=time(9, 0),
            waktu_selesai=time(11, 0),
        )
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()

        create_response = self.client.get(reverse('kalender:kegiatan_create'))
        update_response = self.client.get(reverse('kalender:kegiatan_update', args=[kegiatan.pk]))
        delete_response = self.client.get(reverse('kalender:kegiatan_delete', args=[kegiatan.pk]))

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(update_response.status_code, 404)
        self.assertRedirects(delete_response, reverse('kalender:kegiatan_list'))

    def test_asisten_lab_tidak_melihat_menu_admin_asleb(self):
        self.pengguna.role = 'asisten_lab'
        self.pengguna.save(update_fields=['role'])
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()

        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Inventaris')
        self.assertNotContains(response, 'Barang Tertinggal')
        self.assertNotContains(response, 'Data Aslab')
        self.assertNotContains(response, 'Pendaftaran Aslab')
        self.assertNotContains(response, 'Rekap Honorarium Aslab')
        self.assertNotContains(response, 'Pengguna')

    def test_asisten_lab_tidak_bisa_membuka_menu_admin_asleb_langsung(self):
        self.pengguna.role = 'asisten_lab'
        self.pengguna.save(update_fields=['role'])
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()

        blocked_urls = [
            reverse('inventaris:barang_list'),
            reverse('barang_tertinggal:list'),
            reverse('asleb:asleb_list'),
            reverse('pendaftaran_asleb:pendaftaran_list'),
            reverse('pengguna:list'),
        ]

        for url in blocked_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, reverse('dashboard:home'))

    def test_asisten_lab_bisa_membuat_kegiatan_pribadi_tapi_tidak_mengelola_kegiatan_lain(self):
        self.pengguna.role = 'asisten_lab'
        self.pengguna.save(update_fields=['role'])
        kegiatan = KegiatanKalender.objects.create(
            judul='Workshop IoT',
            tanggal=timezone.localdate(),
            waktu_mulai=time(9, 0),
            waktu_selesai=time(11, 0),
        )
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()

        allowed_urls = [
            reverse('kalender:kegiatan_list'),
            reverse('kalender:kegiatan_detail', args=[kegiatan.pk]),
            reverse('kalender:notifikasi_list'),
        ]

        for url in allowed_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

        create_response = self.client.get(reverse('kalender:kegiatan_create'))
        update_response = self.client.get(reverse('kalender:kegiatan_update', args=[kegiatan.pk]))
        delete_response = self.client.get(reverse('kalender:kegiatan_delete', args=[kegiatan.pk]))

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(update_response.status_code, 404)
        self.assertRedirects(delete_response, reverse('kalender:kegiatan_list'))

    def test_laboran_bisa_membuka_menu_inventaris(self):
        self.pengguna.role = 'laboran'
        self.pengguna.save()
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()

        response = self.client.get(reverse('inventaris:barang_list'))

        self.assertEqual(response.status_code, 200)
