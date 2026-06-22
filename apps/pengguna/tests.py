from django.contrib.auth.hashers import check_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import Pengguna


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
        response = self.client.get(reverse('pengguna:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pengguna')
        self.assertContains(response, self.pengguna.kode_pengguna)
        self.assertContains(response, 'Andi Pratama')
        self.assertContains(response, 'Admin')
        self.assertContains(response, 'data-confirmation-modal')

    def test_create_pengguna_menyimpan_password_hash_dan_foto(self):
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
                'nim_nik': '2201001',
                'password': 'rahasia123',
            },
        )

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(self.client.session['pengguna_id'], self.pengguna.pk)

    def test_login_menolak_password_salah(self):
        response = self.client.post(
            reverse('pengguna:login'),
            {
                'nim_nik': '2201001',
                'password': 'salah',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NIM/NIK atau password tidak sesuai.')
        self.assertNotIn('pengguna_id', self.client.session)

    def test_register_membuat_pengguna_dan_login(self):
        response = self.client.post(
            reverse('pengguna:register'),
            {
                'nama_pengguna': 'Siti Aminah',
                'nim_nik': '2201002',
                'email': 'siti@example.com',
                'password': 'passwordku123',
                'password_confirmation': 'passwordku123',
                'no_hp': '081111111111',
                'alamat': 'Jakarta',
                'fakultas': 'Ekonomi',
                'prodi': 'Manajemen',
                'gender': 'perempuan',
            },
        )

        pengguna = Pengguna.objects.get(nim_nik='2201002')
        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertTrue(check_password('passwordku123', pengguna.password))
        self.assertEqual(pengguna.role, 'mahasiswa')
        self.assertEqual(self.client.session['pengguna_id'], pengguna.pk)

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
        blocked_response = self.client.get(reverse('inventaris:barang_list'))

        self.assertEqual(allowed_response.status_code, 200)
        self.assertContains(allowed_response, 'Dashboard')
        self.assertContains(allowed_response, 'Peminjaman Alat')
        self.assertContains(allowed_response, 'Jadwal Praktikum')
        self.assertNotContains(allowed_response, 'Inventaris')
        self.assertNotContains(allowed_response, 'Pengguna')
        self.assertRedirects(blocked_response, reverse('dashboard:home'))

    def test_laboran_bisa_membuka_menu_inventaris(self):
        self.pengguna.role = 'laboran'
        self.pengguna.save()
        session = self.client.session
        session['pengguna_id'] = self.pengguna.pk
        session.save()

        response = self.client.get(reverse('inventaris:barang_list'))

        self.assertEqual(response.status_code, 200)
