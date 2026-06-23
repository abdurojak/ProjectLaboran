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

    def test_detail_pengguna_tidak_menampilkan_tombol_hapus(self):
        response = self.client.get(reverse('pengguna:detail', args=[self.pengguna.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Profil')
        self.assertContains(response, 'Ganti Password')
        self.assertNotContains(response, 'Konfirmasi Hapus Pengguna')
        self.assertNotContains(response, f'href="{reverse("pengguna:delete", args=[self.pengguna.pk])}"')

    def test_update_profile_mengubah_data_pengguna(self):
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
        self.assertEqual(self.pengguna.role, 'laboran')

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

    def test_login_menolak_akun_belum_terverifikasi(self):
        self.pengguna.is_verified = False
        self.pengguna.save(update_fields=['is_verified'])

        response = self.client.post(
            reverse('pengguna:login'),
            {
                'nim_nik': '2201001',
                'password': 'rahasia123',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Akun belum diverifikasi')
        self.assertNotIn('pengguna_id', self.client.session)

    def test_register_membuat_pengguna_lalu_verifikasi_otp(self):
        response = self.client.post(
            reverse('pengguna:register'),
            {
                'nama_pengguna': 'Siti Aminah',
                'nim_nik': '2201002',
                'email': 'siti@std.trisakti.ac.id',
                'password': 'passwordku123',
                'password_confirmation': 'passwordku123',
                'verification_method': 'email',
                'no_hp': '081111111111',
                'alamat': 'Jakarta',
                'fakultas': 'Ekonomi',
                'prodi': 'Manajemen',
                'gender': 'perempuan',
            },
        )

        pengguna = Pengguna.objects.get(nim_nik='2201002')
        self.assertRedirects(response, reverse('pengguna:verify_register'))
        self.assertTrue(check_password('passwordku123', pengguna.password))
        self.assertEqual(pengguna.role, 'mahasiswa')
        self.assertFalse(pengguna.is_verified)
        self.assertNotIn('pengguna_id', self.client.session)

        kode = self.client.session['pengguna_otp']['code']
        response = self.client.post(reverse('pengguna:verify_register'), {'kode': kode})
        pengguna.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertTrue(pengguna.is_verified)
        self.assertEqual(self.client.session['pengguna_id'], pengguna.pk)

    def test_register_menolak_email_non_trisakti(self):
        response = self.client.post(
            reverse('pengguna:register'),
            {
                'nama_pengguna': 'Siti Aminah',
                'nim_nik': '2201002',
                'email': 'siti@gmail.com',
                'password': 'passwordku123',
                'password_confirmation': 'passwordku123',
                'verification_method': 'email',
                'no_hp': '081111111111',
                'alamat': 'Jakarta',
                'fakultas': 'Ekonomi',
                'prodi': 'Manajemen',
                'gender': 'perempuan',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email harus menggunakan domain @std.trisakti.ac.id.')
        self.assertFalse(Pengguna.objects.filter(nim_nik='2201002').exists())

    def test_register_menolak_nim_dan_no_hp_berhuruf(self):
        response = self.client.post(
            reverse('pengguna:register'),
            {
                'nama_pengguna': 'Siti Aminah',
                'nim_nik': '2201ABC',
                'email': 'siti@std.trisakti.ac.id',
                'password': 'passwordku123',
                'password_confirmation': 'passwordku123',
                'verification_method': 'no_hp',
                'no_hp': '081ABC',
                'alamat': 'Jakarta',
                'fakultas': 'Ekonomi',
                'prodi': 'Manajemen',
                'gender': 'perempuan',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NIM/NIK hanya boleh berisi angka.')
        self.assertContains(response, 'No HP hanya boleh berisi angka.')

    def test_forgot_password_mengganti_password_dengan_otp(self):
        response = self.client.post(
            reverse('pengguna:forgot_password'),
            {'nim_nik': '2201001', 'verification_method': 'no_hp'},
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
