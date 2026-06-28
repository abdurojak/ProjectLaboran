from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from reportlab.lib.enums import TA_RIGHT

from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb
from apps.pengguna.models import Pengguna

from .forms import AbsensiAslebForm
from .models import AbsensiAsleb, Asleb, HonorAsleb, ModulPraktikum, PengaturanAbsensiAsleb
from .surat_honor import LAB_SIGNATURES, build_lab_signature, build_lampiran_page, build_styles


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
        self.assertContains(response, 'Data Aslab')
        self.assertContains(response, 'Siti Nurhaliza')
        self.assertContains(response, 'Pemrograman Web')
        active_links = [link['title'] for link in response.context['sidebar_links'] if link['active']]
        self.assertEqual(active_links, ['Data Aslab'])

    def test_absensi_list_memakai_layout_responsif(self):
        response = self.client.get(reverse('asleb:absensi_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'min-w-0 max-w-full space-y-6 overflow-hidden')
        self.assertContains(response, '-mx-2 max-w-full overflow-x-auto')
        self.assertContains(response, 'min-w-[860px]')

    def test_absensi_form_memakai_layout_responsif(self):
        PengaturanAbsensiAsleb.get_solo().__class__.objects.update_or_create(pk=1, defaults={'dibuka': True})
        aslab_user = Pengguna.objects.create(
            nama_pengguna='Siti Nurhaliza',
            nim_nik=self.asleb.nim,
            email='siti-aslab-login@example.com',
            password='rahasia123',
            no_hp='081234567891',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
        )
        session = self.client.session
        session['pengguna_id'] = aslab_user.pk
        session.save()

        response = self.client.get(reverse('asleb:absensi_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mx-auto min-w-0 max-w-4xl')
        self.assertContains(response, 'min-w-0 max-w-full overflow-hidden')
        self.assertContains(response, 'w-full justify-center sm:w-auto')

    def test_asisten_lab_tidak_dapat_menambah_modul(self):
        aslab_user = Pengguna.objects.create(
            nama_pengguna='Siti Nurhaliza',
            nim_nik=self.asleb.nim,
            email='siti-modul@example.com',
            password='rahasia123',
            no_hp='081234567891',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
        )
        session = self.client.session
        session['pengguna_id'] = aslab_user.pk
        session.save()

        response = self.client.get(reverse('asleb:modul_create'))

        self.assertRedirects(response, reverse('dashboard:home'))

    def test_laboran_dapat_menambah_modul_matkul(self):
        laboran = Pengguna.objects.create(
            nama_pengguna='Laboran Modul',
            nim_nik='1000000099',
            email='laboran-modul@example.com',
            password='rahasia123',
            no_hp='081234567899',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        session = self.client.session
        session['pengguna_id'] = laboran.pk
        session.save()

        response = self.client.post(reverse('asleb:modul_create'), {
            'matkul': self.matkul.pk,
            'nomor': 1,
            'judul': 'Pengenalan Struktur Data',
            'file': SimpleUploadedFile('modul-sda.pdf', b'isi modul', content_type='application/pdf'),
        })

        self.assertRedirects(response, reverse('asleb:absensi_list'))
        self.assertTrue(ModulPraktikum.objects.filter(matkul=self.matkul, nomor=1, diunggah_oleh=laboran).exists())

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
        self.assertContains(response, 'Rekap Honorarium Aslab')
        self.assertContains(response, 'Siti Nurhaliza')
        self.assertContains(response, 'Rp 147.000')
        self.assertContains(response, 'BCA 123456789')
        active_links = [link['title'] for link in response.context['sidebar_links'] if link['active']]
        self.assertEqual(active_links, ['Rekap Honorarium Aslab'])

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

    def test_ttd_kepala_laboratorium_di_lampiran_rata_kanan(self):
        lab_name = next(iter(LAB_SIGNATURES))
        honor = HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 4, 1),
            jumlah_praktikum=1,
            total_pertemuan=3,
            status='diproses',
        )

        story = build_lampiran_page(build_styles(), lab_name, [honor], 'April 2026')
        signature_wrapper = story[-1]
        signature = signature_wrapper._cellvalues[0][1]

        self.assertEqual(signature_wrapper._colWidths[0] > signature_wrapper._colWidths[1], True)
        self.assertEqual(signature._cellvalues[0][0].style.alignment, TA_RIGHT)
        self.assertEqual(signature._cellvalues[2][0].style.alignment, TA_RIGHT)
        self.assertEqual(build_lab_signature(build_styles(), lab_name)._cellvalues[0][1]._cellvalues[2][0].text, LAB_SIGNATURES[lab_name])

    def test_absensi_menolak_modul_yang_sudah_dipakai(self):
        PendaftaranAsleb.objects.create(
            nama=self.asleb.nama,
            nim=self.asleb.nim,
            no_hp=self.asleb.no_hp,
            email=self.asleb.email,
            program_studi=self.asleb.program_studi,
            semester=self.asleb.semester,
            matkul=self.matkul,
            status='digenerate',
        )
        modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=1,
            judul='Pengenalan Struktur Data',
            file=SimpleUploadedFile('modul-1.pdf', b'isi modul', content_type='application/pdf'),
        )
        first_form = AbsensiAslebForm(
            data={
                'tanggal_praktikum': '2026-04-01',
                'modul_praktikum': modul.pk,
                'pekerjaan': 'Membantu praktikum',
            },
            files={
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
                'modul_praktikum': modul.pk,
                'pekerjaan': 'Membantu praktikum',
            },
            files={
                'bukti_video': SimpleUploadedFile('video-2.mp4', b'video 2', content_type='video/mp4'),
            },
            asleb=self.asleb,
        )

        self.assertFalse(second_form.is_valid())
        self.assertIn('modul_praktikum', second_form.errors)

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
