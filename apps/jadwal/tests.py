from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.pengguna.models import Pengguna

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

        JadwalPraktikum.objects.create(
            mata_kuliah='Praktikum Basis Data',
            kelas='XI RPL 1',
            letak_ruangan='Lab Rekayasa Data',
            pengampu='Ibu Sari',
            tanggal=date(2026, 6, 18),
            waktu_mulai=time(8, 0),
            waktu_selesai=time(10, 0),
        )

    def test_jadwal_page_loads(self):
        response = self.client.get(reverse('jadwal:jadwal_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jadwal Praktikum')
        self.assertContains(response, 'Praktikum Basis Data')
        self.assertContains(response, 'Lab Rekayasa Data')

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
            letak_ruangan='Lab Rekayasa Data',
            pengampu='Pak Budi',
            tanggal=date(2026, 6, 18),
            waktu_mulai=time(9, 0),
            waktu_selesai=time(11, 0),
        )

        with self.assertRaises(ValidationError):
            jadwal_bentrok.full_clean()

    def test_jadwal_boleh_jika_waktu_berurutan_di_ruangan_sama(self):
        jadwal_lanjutan = JadwalPraktikum(
            mata_kuliah='Praktikum Jaringan',
            kelas='XI RPL 3',
            letak_ruangan='Lab Rekayasa Data',
            pengampu='Pak Dimas',
            tanggal=date(2026, 6, 18),
            waktu_mulai=time(10, 0),
            waktu_selesai=time(12, 0),
        )

        jadwal_lanjutan.full_clean()

