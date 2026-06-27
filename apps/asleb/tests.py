from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb
from apps.pengguna.models import Pengguna

from .forms import AbsensiAslebForm
from .models import Asleb, HonorAsleb


class AslebViewTests(TestCase):
    def setUp(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='Lab Admin',
            nim_nik='ADM-ASLEB',
            email='admin-asleb@example.com',
            password='rahasia123',
            no_hp='081234567800',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='admin',
        )
        self.matkul = MataKuliahAsleb.objects.get(kode='SDA_TIF01_ABDUL')
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()

        self.asleb = Asleb.objects.create(
            nama='Siti Nurhaliza',
            nim='2301001',
            no_hp='081234567890',
            email='siti@example.com',
            program_studi='Rekayasa Perangkat Lunak',
            matkul='Pemrograman Web',
            semester=4,
            tanggal_bergabung=date(2026, 6, 22),
        )

    def test_asleb_list_page_loads(self):
        response = self.client.get(reverse('asleb:asleb_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Data Asleb')
        self.assertContains(response, 'Siti Nurhaliza')
        self.assertContains(response, 'Pemrograman Web')
        active_links = [link['title'] for link in response.context['sidebar_links'] if link['active']]
        self.assertEqual(active_links, ['Data Asleb'])

    def test_asleb_search_filters_data(self):
        response = self.client.get(reverse('asleb:asleb_list'), {'q': '2301001'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Siti Nurhaliza')

    def test_asleb_search_filters_by_matkul(self):
        response = self.client.get(reverse('asleb:asleb_list'), {'q': 'Pemrograman Web'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Siti Nurhaliza')

    def test_honor_asleb_mengikuti_rumus_excel(self):
        self.create_pendaftaran_history(self.asleb.nim, 3)

        honor = HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 4, 1),
            level='junior',
            jumlah_praktikum=2,
            total_pertemuan=10,
            pic_transfer='Faiz',
            status='diproses',
        )

        self.assertEqual(honor.total_jam_terealisasi, 70)
        self.assertEqual(honor.total_akhir, 60)
        self.assertEqual(honor.level, 'senior')
        self.assertEqual(honor.honor_per_jam, 8000)
        self.assertEqual(honor.jumlah, 480000)
        self.assertEqual(honor.metode_transfer, 'rekening_bank')
        self.assertEqual(honor.nomor_transfer, 'BCA 123456789')
        self.assertEqual(honor.nama_pemilik_transfer, 'Riwayat Asleb 3')

    def test_honor_asleb_dua_periode_masih_junior(self):
        self.create_pendaftaran_history(self.asleb.nim, 2)

        honor = HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 4, 1),
            level='senior',
            jumlah_praktikum=1,
            total_pertemuan=3,
            pic_transfer='Faiz',
            status='diproses',
        )

        self.assertEqual(honor.level, 'junior')
        self.assertEqual(honor.honor_per_jam, 7000)
        self.assertEqual(honor.jumlah, 147000)

    def test_honor_list_page_loads(self):
        self.create_pendaftaran_history(self.asleb.nim, 1)

        HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 4, 1),
            level='junior',
            jumlah_praktikum=1,
            total_pertemuan=3,
            pic_transfer='Faiz',
            status='diproses',
        )

        response = self.client.get(reverse('asleb:honor_list'), {'bulan': '2026-04'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rekap Honorarium Asleb')
        self.assertContains(response, 'Siti Nurhaliza')
        self.assertContains(response, 'Rp 147.000')
        self.assertContains(response, 'BCA 123456789')
        active_links = [link['title'] for link in response.context['sidebar_links'] if link['active']]
        self.assertEqual(active_links, ['Rekap Honorarium Asleb'])

    def test_konfirmasi_transfer_honor_menyimpan_bukti_dan_status_dibayar(self):
        honor = HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 4, 1),
            jumlah_praktikum=1,
            total_pertemuan=3,
            status='diproses',
        )
        bukti = SimpleUploadedFile('bukti-tf.jpg', b'bukti transfer', content_type='image/jpeg')

        response = self.client.post(reverse('asleb:honor_confirm_transfer', args=[honor.pk]), {
            'tanggal_transfer': '2026-04-30',
            'pic_transfer': 'Lab Admin',
            'bukti_transfer': bukti,
        })

        self.assertRedirects(response, reverse('asleb:honor_list'))
        honor.refresh_from_db()
        self.assertEqual(honor.status, 'dibayar')
        self.assertEqual(honor.pic_transfer, 'Lab Admin')
        self.assertTrue(honor.bukti_transfer)

    def test_absensi_menolak_file_modul_yang_sama(self):
        first_form = AbsensiAslebForm(
            data={
                'tanggal_praktikum': '2026-04-01',
                'modul': 1,
                'materi_praktikum': 'Materi 1',
                'pekerjaan': 'Membantu praktikum',
            },
            files={
                'file_modul': SimpleUploadedFile('modul-1.pdf', b'isi modul sama', content_type='application/pdf'),
                'bukti_video': SimpleUploadedFile('video-1.mp4', b'video 1', content_type='video/mp4'),
            },
            asleb=self.asleb,
        )
        self.assertTrue(first_form.is_valid(), first_form.errors)
        first_absensi = first_form.save(commit=False)
        first_absensi.asleb = self.asleb
        first_absensi.save()

        second_form = AbsensiAslebForm(
            data={
                'tanggal_praktikum': '2026-04-02',
                'modul': 2,
                'materi_praktikum': 'Materi 2',
                'pekerjaan': 'Membantu praktikum',
            },
            files={
                'file_modul': SimpleUploadedFile('modul-duplikat.pdf', b'isi modul sama', content_type='application/pdf'),
                'bukti_video': SimpleUploadedFile('video-2.mp4', b'video 2', content_type='video/mp4'),
            },
            asleb=self.asleb,
        )

        self.assertFalse(second_form.is_valid())
        self.assertIn('file_modul', second_form.errors)

    def create_pendaftaran_history(self, nim, count):
        for index in range(count):
            PendaftaranAsleb.objects.create(
                nama=f'Riwayat Asleb {index + 1}',
                nim=nim,
                no_hp='081234567890',
                email=f'riwayat{index + 1}@std.trisakti.ac.id',
                program_studi='Rekayasa Perangkat Lunak',
                semester=4,
                matkul=self.matkul,
                metode_rekening='rekening_bank',
                rekening='BCA 123456789',
                status='digenerate',
            )
