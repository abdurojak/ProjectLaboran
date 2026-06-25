from datetime import time

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.pengguna.models import Pengguna
from apps.ruangan.models import RuanganLab

from .models import JadwalPraktikum


class JadwalViewTests(TestCase):
    def setUp(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='Lab Admin',
            nim_nik='ADM-JADWAL',
            email='admin-jadwal@example.com',
            password='rahasia123',
            no_hp='081234567801',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()

        self.ruangan = RuanganLab.objects.create(
            nama='Lab Rekayasa Data',
            kode='LAB-RD-TEST',
            deskripsi='Lab untuk pengujian jadwal.',
            kapasitas=30,
            warna='violet',
        )
        JadwalPraktikum.objects.create(
            mata_kuliah='Praktikum Basis Data',
            kelas='XI RPL 1',
            ruangan=self.ruangan,
            pengampu='Ibu Sari',
            hari='kamis',
            waktu_mulai=time(8, 0),
            waktu_selesai=time(10, 0),
        )

    def test_jadwal_page_loads(self):
        response = self.client.get(reverse('jadwal:jadwal_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jadwal Praktikum')
        self.assertContains(response, 'Praktikum Basis Data')
        self.assertContains(response, 'Lab Rekayasa Data')
        self.assertContains(response, 'Senin')
        self.assertContains(response, 'Sabtu')
        self.assertNotContains(response, 'Minggu')

    def test_jadwal_list_menampilkan_grid_berdasarkan_hari_dan_ruangan(self):
        response = self.client.get(reverse('jadwal:jadwal_list'), {'hari': 'kamis'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '7:30')
        self.assertContains(response, '18:00')
        self.assertContains(response, 'Lab Rekayasa Data (30)')
        self.assertContains(response, 'Praktikum Basis Data')
        self.assertContains(response, 'XI RPL 1')
        self.assertContains(response, 'Ibu Sari')

    def test_jadwal_dengan_jam_tidak_persis_slot_tetap_tampil(self):
        JadwalPraktikum.objects.create(
            mata_kuliah='Praktikum Jaringan',
            kelas='TI 4B',
            ruangan=self.ruangan,
            pengampu='Pak Dimas',
            hari='kamis',
            waktu_mulai=time(10, 19),
            waktu_selesai=time(11, 19),
        )

        response = self.client.get(reverse('jadwal:jadwal_list'), {'hari': 'kamis'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Praktikum Jaringan')

    def test_form_jadwal_memakai_hari_bukan_tanggal(self):
        response = self.client.get(reverse('jadwal:jadwal_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="hari"', html=False)
        self.assertContains(response, 'Senin')
        self.assertContains(response, 'Sabtu')
        self.assertContains(response, 'name="ruangan"', html=False)
        self.assertContains(response, 'step="1800"', html=False)
        self.assertContains(response, 'min="07:30"', html=False)
        self.assertContains(response, 'max="18:00"', html=False)
        self.assertNotContains(response, 'name="tanggal"', html=False)

    def login_as_mahasiswa(self):
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
        return mahasiswa

    def test_aksi_kelola_jadwal_disembunyikan_untuk_mahasiswa(self):
        self.login_as_mahasiswa()

        response = self.client.get(reverse('jadwal:jadwal_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Tambah Jadwal')
        self.assertNotContains(response, reverse('jadwal:jadwal_create'))
        self.assertNotContains(response, 'Edit')
        self.assertNotContains(response, reverse('jadwal:jadwal_update', args=[JadwalPraktikum.objects.first().pk]))
        self.assertNotContains(response, f'action="{reverse("jadwal:jadwal_delete", args=[JadwalPraktikum.objects.first().pk])}"')

    def test_mahasiswa_tidak_bisa_create_update_delete_jadwal_lewat_url(self):
        self.login_as_mahasiswa()
        jadwal = JadwalPraktikum.objects.first()

        create_response = self.client.get(reverse('jadwal:jadwal_create'))
        update_response = self.client.get(reverse('jadwal:jadwal_update', args=[jadwal.pk]))
        delete_response = self.client.post(reverse('jadwal:jadwal_delete', args=[jadwal.pk]))

        self.assertRedirects(create_response, reverse('jadwal:jadwal_list'))
        self.assertRedirects(update_response, reverse('jadwal:jadwal_list'))
        self.assertRedirects(delete_response, reverse('jadwal:jadwal_list'))
        self.assertTrue(JadwalPraktikum.objects.filter(pk=jadwal.pk).exists())

    def test_jadwal_tidak_bisa_bentrok_ruangan_dan_waktu(self):
        jadwal_bentrok = JadwalPraktikum(
            mata_kuliah='Praktikum Pemrograman',
            kelas='XI RPL 2',
            ruangan=self.ruangan,
            pengampu='Pak Budi',
            hari='kamis',
            waktu_mulai=time(9, 0),
            waktu_selesai=time(11, 0),
        )

        with self.assertRaises(ValidationError):
            jadwal_bentrok.full_clean()

    def test_jadwal_boleh_jika_waktu_berurutan_di_ruangan_sama(self):
        jadwal_lanjutan = JadwalPraktikum(
            mata_kuliah='Praktikum Jaringan',
            kelas='XI RPL 3',
            ruangan=self.ruangan,
            pengampu='Pak Dimas',
            hari='kamis',
            waktu_mulai=time(10, 0),
            waktu_selesai=time(12, 0),
        )

        jadwal_lanjutan.full_clean()

    def test_jadwal_tidak_bisa_di_luar_jam_kerja(self):
        kasus_jam = [
            (time(7, 0), time(8, 0)),
            (time(17, 30), time(18, 30)),
            (time(18, 0), time(18, 30)),
        ]

        for waktu_mulai, waktu_selesai in kasus_jam:
            with self.subTest(waktu_mulai=waktu_mulai, waktu_selesai=waktu_selesai):
                jadwal = JadwalPraktikum(
                    mata_kuliah='Praktikum Di Luar Jam',
                    kelas='TI 4C',
                    ruangan=self.ruangan,
                    pengampu='Pak Dimas',
                    hari='kamis',
                    waktu_mulai=waktu_mulai,
                    waktu_selesai=waktu_selesai,
                )

                with self.assertRaises(ValidationError):
                    jadwal.full_clean()

