from datetime import time

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb
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
        self.matkul = MataKuliahAsleb.objects.create(
            kode='TEST_JADWAL_BASIS_DATA',
            nama='Praktikum Basis Data',
            dosen='Ibu Sari',
            kelas='XI RPL 1',
        )
        self.matkul_lain = MataKuliahAsleb.objects.create(
            kode='TEST_JADWAL_JARINGAN',
            nama='Praktikum Jaringan',
            dosen='Pak Dimas',
            kelas='TI 4B',
        )
        JadwalPraktikum.objects.create(
            mata_kuliah=str(self.matkul),
            kelas='XI RPL 1',
            ruangan=self.ruangan,
            pengampu='Ibu Sari',
            hari='kamis',
            waktu_mulai=time(8, 0),
            waktu_selesai=time(10, 0),
            status=JadwalPraktikum.STATUS_DITERIMA,
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
        self.assertContains(response, 'jadwal-board')
        self.assertContains(response, 'jadwal-lab-scroll')
        self.assertContains(response, 'jadwal-time-panel')
        self.assertContains(response, 'jadwal-room-track')
        self.assertContains(response, 'jadwal-slot-grid')
        self.assertContains(response, 'flex flex-wrap gap-2')
        self.assertNotContains(response, 'Ruang Lab')
        self.assertContains(response, '7:30')
        self.assertContains(response, '18:00')
        self.assertContains(response, 'Lab Rekayasa Data (30)')
        self.assertContains(response, 'Praktikum Basis Data')
        self.assertNotContains(response, 'z-10 p-1.5')
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
            status=JadwalPraktikum.STATUS_DITERIMA,
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
        self.assertContains(response, 'name="matkul"', html=False)
        self.assertContains(response, str(self.matkul))
        self.assertContains(response, 'step="1800"', html=False)
        self.assertContains(response, 'min="07:30"', html=False)
        self.assertContains(response, 'max="18:00"', html=False)
        self.assertNotContains(response, 'name="tanggal"', html=False)
        self.assertNotContains(response, 'name="mata_kuliah"', html=False)
        self.assertNotContains(response, 'name="kelas"', html=False)
        self.assertNotContains(response, 'name="pengampu"', html=False)

    def test_form_jadwal_menyimpan_matkul_kelas_dan_pengampu_dari_pilihan_matkul(self):
        response = self.client.post(reverse('jadwal:jadwal_create'), {
            'matkul': self.matkul_lain.pk,
            'ruangan': self.ruangan.pk,
            'hari': 'rabu',
            'waktu_mulai': '13:00',
            'waktu_selesai': '14:00',
            'catatan': '',
        })

        self.assertRedirects(response, reverse('jadwal:jadwal_list'))
        jadwal = JadwalPraktikum.objects.get(hari='rabu')
        self.assertEqual(jadwal.mata_kuliah, str(self.matkul_lain))
        self.assertEqual(jadwal.kelas, self.matkul_lain.kelas)
        self.assertEqual(jadwal.pengampu, self.matkul_lain.dosen)

    def test_form_jadwal_menampilkan_error_validasi_berwarna_merah(self):
        response = self.client.post(reverse('jadwal:jadwal_create'), {
            'matkul': self.matkul.pk,
            'ruangan': self.ruangan.pk,
            'hari': 'kamis',
            'waktu_mulai': '18:00',
            'waktu_selesai': '18:30',
            'catatan': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<p class="mt-2 text-sm font-semibold text-rose-600">Waktu mulai harus berada dalam jam kerja', html=False)

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

    def login_as_asisten_lab(self):
        aslab = Pengguna.objects.create(
            nama_pengguna='Aslab Jadwal',
            nim_nik='2201003',
            email='aslab-jadwal@example.com',
            password='rahasia123',
            no_hp='081111111112',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='asisten_lab',
        )
        session = self.client.session
        session['pengguna_id'] = aslab.pk
        session.save()
        return aslab

    def test_form_jadwal_aslab_hanya_menampilkan_matkul_yang_diterima_atau_digenerate(self):
        aslab = self.login_as_asisten_lab()
        PendaftaranAsleb.objects.create(
            nama=aslab.nama_pengguna,
            nim=aslab.nim_nik,
            no_hp=aslab.no_hp,
            email=aslab.email,
            program_studi=aslab.prodi,
            semester=5,
            matkul=self.matkul,
            status='digenerate',
        )
        PendaftaranAsleb.objects.create(
            nama=aslab.nama_pengguna,
            nim=aslab.nim_nik,
            no_hp=aslab.no_hp,
            email=aslab.email,
            program_studi=aslab.prodi,
            semester=5,
            matkul=self.matkul_lain,
            status='ditolak',
        )

        response = self.client.get(reverse('jadwal:jadwal_create'))

        self.assertContains(response, str(self.matkul))
        self.assertNotContains(response, str(self.matkul_lain))

    def test_aslab_tidak_bisa_mengajukan_jadwal_dengan_matkul_yang_bukan_miliknya(self):
        aslab = self.login_as_asisten_lab()
        PendaftaranAsleb.objects.create(
            nama=aslab.nama_pengguna,
            nim=aslab.nim_nik,
            no_hp=aslab.no_hp,
            email=aslab.email,
            program_studi=aslab.prodi,
            semester=5,
            matkul=self.matkul,
            status='digenerate',
        )

        response = self.client.post(reverse('jadwal:jadwal_create'), {
            'matkul': self.matkul_lain.pk,
            'ruangan': self.ruangan.pk,
            'hari': 'rabu',
            'waktu_mulai': '13:00',
            'waktu_selesai': '14:00',
            'catatan': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(JadwalPraktikum.objects.filter(hari='rabu').exists())

    def test_aslab_melihat_list_praktikum_saya_berdasarkan_matkulnya(self):
        aslab = self.login_as_asisten_lab()
        PendaftaranAsleb.objects.create(
            nama=aslab.nama_pengguna,
            nim=aslab.nim_nik,
            no_hp=aslab.no_hp,
            email=aslab.email,
            program_studi=aslab.prodi,
            semester=5,
            matkul=self.matkul,
            status='digenerate',
        )
        JadwalPraktikum.objects.create(
            mata_kuliah=str(self.matkul),
            kelas=self.matkul.kelas,
            ruangan=self.ruangan,
            pengampu=self.matkul.dosen,
            hari='rabu',
            waktu_mulai=time(13, 0),
            waktu_selesai=time(14, 0),
            status=JadwalPraktikum.STATUS_DIAJUKAN,
        )
        JadwalPraktikum.objects.create(
            mata_kuliah=str(self.matkul_lain),
            kelas=self.matkul_lain.kelas,
            ruangan=self.ruangan,
            pengampu=self.matkul_lain.dosen,
            hari='rabu',
            waktu_mulai=time(14, 0),
            waktu_selesai=time(15, 0),
            status=JadwalPraktikum.STATUS_DIAJUKAN,
        )

        response = self.client.get(reverse('jadwal:jadwal_list'), {'hari': 'rabu'})

        self.assertContains(response, 'Praktikum Saya')
        self.assertContains(response, str(self.matkul))
        self.assertContains(response, 'Diajukan')
        self.assertNotContains(response, str(self.matkul_lain))

    def test_aksi_kelola_jadwal_disembunyikan_untuk_mahasiswa(self):
        self.login_as_mahasiswa()

        response = self.client.get(reverse('jadwal:jadwal_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Tambah Jadwal')
        self.assertNotContains(response, reverse('jadwal:jadwal_create'))
        self.assertNotContains(response, 'Edit')
        self.assertNotContains(response, reverse('jadwal:jadwal_update', args=[JadwalPraktikum.objects.first().pk]))
        self.assertNotContains(response, f'action="{reverse("jadwal:jadwal_delete", args=[JadwalPraktikum.objects.first().pk])}"')

        detail_response = self.client.get(reverse('jadwal:jadwal_detail', args=[JadwalPraktikum.objects.first().pk]))
        self.assertNotContains(detail_response, reverse('jadwal:jadwal_update', args=[JadwalPraktikum.objects.first().pk]))

    def test_mahasiswa_tidak_melihat_jadwal_yang_masih_diajukan(self):
        self.login_as_mahasiswa()
        jadwal_diajukan = JadwalPraktikum.objects.create(
            mata_kuliah='Praktikum Menunggu',
            kelas='TI 6A',
            ruangan=self.ruangan,
            pengampu='Pak Dimas',
            hari='kamis',
            waktu_mulai=time(13, 0),
            waktu_selesai=time(14, 0),
            status=JadwalPraktikum.STATUS_DIAJUKAN,
        )

        response = self.client.get(reverse('jadwal:jadwal_list'), {'hari': 'kamis'})

        self.assertContains(response, 'Praktikum Basis Data')
        self.assertNotContains(response, 'Praktikum Menunggu')

        detail_response = self.client.get(reverse('jadwal:jadwal_detail', args=[jadwal_diajukan.pk]))
        self.assertEqual(detail_response.status_code, 404)

    def test_cell_jadwal_semua_role_tidak_menduplikasi_kelas_dan_dosen(self):
        roles = [
            ('mahasiswa', self.login_as_mahasiswa),
            ('asisten_lab', self.login_as_asisten_lab),
        ]

        for role, login in roles:
            with self.subTest(role=role):
                login()
                response = self.client.get(reverse('jadwal:jadwal_list'), {'hari': 'kamis'})

                self.assertContains(response, 'XI RPL 1')
                self.assertContains(response, 'Ibu Sari')
                self.assertNotContains(response, 'jadwal-kelas')
                self.assertNotContains(response, 'jadwal-pengampu')

    def test_aslab_hanya_bisa_mengelola_jadwal_praktikum_miliknya(self):
        aslab = self.login_as_asisten_lab()
        PendaftaranAsleb.objects.create(
            nama=aslab.nama_pengguna,
            nim=aslab.nim_nik,
            no_hp=aslab.no_hp,
            email=aslab.email,
            program_studi=aslab.prodi,
            semester=5,
            matkul=self.matkul,
            status='digenerate',
        )
        jadwal_milik_aslab = JadwalPraktikum.objects.first()
        jadwal_lain = JadwalPraktikum.objects.create(
            mata_kuliah=str(self.matkul_lain),
            kelas=self.matkul_lain.kelas,
            ruangan=self.ruangan,
            pengampu=self.matkul_lain.dosen,
            hari='kamis',
            waktu_mulai=time(13, 0),
            waktu_selesai=time(14, 0),
            status=JadwalPraktikum.STATUS_DITERIMA,
        )

        response = self.client.get(reverse('jadwal:jadwal_list'), {'hari': 'kamis'})

        self.assertContains(response, reverse('jadwal:jadwal_update', args=[jadwal_milik_aslab.pk]))
        self.assertContains(response, f'action="{reverse("jadwal:jadwal_delete", args=[jadwal_milik_aslab.pk])}"')
        self.assertNotContains(response, reverse('jadwal:jadwal_update', args=[jadwal_lain.pk]))
        self.assertNotContains(response, f'action="{reverse("jadwal:jadwal_delete", args=[jadwal_lain.pk])}"')

        update_response = self.client.get(reverse('jadwal:jadwal_update', args=[jadwal_lain.pk]))
        delete_response = self.client.post(reverse('jadwal:jadwal_delete', args=[jadwal_lain.pk]))

        self.assertEqual(update_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(JadwalPraktikum.objects.filter(pk=jadwal_lain.pk).exists())

    def test_jadwal_list_hanya_menampilkan_jadwal_diterima_tanpa_badge_status(self):
        JadwalPraktikum.objects.create(
            mata_kuliah='Praktikum Menunggu Admin',
            kelas='TI 6B',
            ruangan=self.ruangan,
            pengampu='Asleb Dua',
            hari='kamis',
            waktu_mulai=time(13, 0),
            waktu_selesai=time(14, 0),
            status=JadwalPraktikum.STATUS_DIAJUKAN,
        )

        response = self.client.get(reverse('jadwal:jadwal_list'), {'hari': 'kamis'})

        self.assertContains(response, 'Praktikum Basis Data')
        self.assertNotContains(response, 'Praktikum Menunggu Admin')
        self.assertNotContains(response, 'Diajukan')
        self.assertNotContains(response, 'Diterima')

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
            status=JadwalPraktikum.STATUS_DITERIMA,
        )

        with self.assertRaises(ValidationError):
            jadwal_bentrok.full_clean()

    def test_jadwal_diajukan_boleh_bentrok_dengan_jadwal_lain(self):
        jadwal_diajukan = JadwalPraktikum(
            mata_kuliah='Praktikum Pengajuan Bentrok',
            kelas='XI RPL 2',
            ruangan=self.ruangan,
            pengampu='Pak Budi',
            hari='kamis',
            waktu_mulai=time(9, 0),
            waktu_selesai=time(11, 0),
            status=JadwalPraktikum.STATUS_DIAJUKAN,
        )

        jadwal_diajukan.full_clean()

    def test_jadwal_boleh_jika_waktu_berurutan_di_ruangan_sama(self):
        jadwal_lanjutan = JadwalPraktikum(
            mata_kuliah='Praktikum Jaringan',
            kelas='XI RPL 3',
            ruangan=self.ruangan,
            pengampu='Pak Dimas',
            hari='kamis',
            waktu_mulai=time(10, 0),
            waktu_selesai=time(12, 0),
            status=JadwalPraktikum.STATUS_DITERIMA,
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
                    status=JadwalPraktikum.STATUS_DITERIMA,
                )

                with self.assertRaises(ValidationError):
                    jadwal.full_clean()

