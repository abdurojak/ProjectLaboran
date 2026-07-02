import base64
import shutil
import tempfile
from datetime import date, datetime
from unittest import skipUnless
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from reportlab.lib.enums import TA_RIGHT

from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb
from apps.pengguna.models import Pengguna
from apps.jadwal.models import JadwalPraktikum
from apps.ruangan.models import RuanganLab

from .forms import AbsensiAslebForm, ENABLE_CAMERA_LOCATION_CAPTURE
from .models import AbsensiAsleb, Asleb, HonorAsleb, ModulPraktikum, PengaturanAbsensiAsleb, PesertaPraktikum
from .surat_honor import LAB_SIGNATURES, build_lab_signature, build_lampiran_page, build_styles


class AslebViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._temp_media_root = tempfile.mkdtemp(prefix='asleb-test-media-')
        cls._media_override = override_settings(MEDIA_ROOT=cls._temp_media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._temp_media_root, ignore_errors=True)
        super().tearDownClass()

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
        self.matkul, _ = MataKuliahAsleb.objects.get_or_create(
            kode='SDA_TIF01_ABDUL',
            defaults={
                'nama': 'Struktur Data dan Algoritma',
                'dosen': 'Abdul Roohman',
                'kelas': 'TIF-01',
            },
        )
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
        self.assertEqual(active_links, ['Asisten Laboratorium'])
        asleb_group = next(link for link in response.context['sidebar_links'] if link['title'] == 'Asisten Laboratorium')
        self.assertEqual([child['title'] for child in asleb_group['children'] if child['active']], ['Data Aslab'])

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

    def make_camera_photo(self, name='bukti.png'):
        image = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        return SimpleUploadedFile(name, image, content_type='image/png')

    def test_form_absensi_menyediakan_upload_bukti_foto_dan_video_manual(self):
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
        ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=7,
            judul='Graph',
            file=SimpleUploadedFile('modul-7.pdf', b'isi modul', content_type='application/pdf'),
        )

        form = AbsensiAslebForm(asleb=self.asleb, jadwal=self.create_active_schedule())

        self.assertEqual(form.fields['bukti_foto'].label, 'Upload Bukti Foto')
        self.assertTrue(form.fields['bukti_foto'].required)
        self.assertIn('image/jpeg,image/png', form.fields['bukti_foto'].widget.attrs.get('accept', ''))
        self.assertEqual(form.fields['bukti_video'].label, 'Upload Bukti Video')
        self.assertTrue(form.fields['bukti_video'].required)
        self.assertIn('video/webm,video/mp4', form.fields['bukti_video'].widget.attrs.get('accept', ''))

    def test_daftar_absensi_aman_jika_bukti_video_kosong(self):
        modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=8,
            judul='Hashing',
            file=SimpleUploadedFile('modul-8.pdf', b'isi modul', content_type='application/pdf'),
        )
        AbsensiAsleb.objects.create(
            asleb=self.asleb,
            jadwal=self.create_active_schedule(),
            modul_praktikum=modul,
            tanggal_praktikum=date(2026, 6, 24),
            modul=8,
            materi_praktikum='Hashing',
            pekerjaan='Absensi lama tanpa video',
            file_modul=SimpleUploadedFile('modul-lama.pdf', b'isi modul', content_type='application/pdf'),
        )

        response = self.client.get(reverse('asleb:absensi_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hashing')
        self.assertContains(response, '<span class="text-slate-400">-</span>', html=True)

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

    def test_laboran_dapat_membuka_absensi_aslab(self):
        laboran = Pengguna.objects.create(
            nama_pengguna='Laboran Absensi',
            nim_nik='1000000098',
            email='laboran-absensi@example.com',
            password='rahasia123',
            no_hp='081234567898',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        session = self.client.session
        session['pengguna_id'] = laboran.pk
        session.save()

        response = self.client.post(reverse('asleb:absensi_toggle_status'))

        self.assertRedirects(response, reverse('asleb:absensi_list'))
        self.assertTrue(PengaturanAbsensiAsleb.get_solo().dibuka)

    def test_asleb_search_filters_data(self):
        response = self.client.get(reverse('asleb:asleb_list'), {'q': '2301001'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Siti Nurhaliza')

    def test_asleb_search_filters_by_matkul(self):
        response = self.client.get(reverse('asleb:asleb_list'), {'q': 'Pemrograman Web'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Siti Nurhaliza')

    def test_laboran_dapat_mengeluarkan_asleb_dan_role_kembali_mahasiswa(self):
        laboran = Pengguna.objects.create(
            nama_pengguna='Laboran Terminasi', nim_nik='LAB-TERM',
            email='laboran-term@trisakti.ac.id', password='rahasia123',
            no_hp='081200000099', alamat='Jakarta', fakultas='Teknologi Industri',
            prodi='Informatika', gender='laki_laki', role='laboran', is_verified=True,
        )
        akun_asleb = Pengguna.objects.create(
            nama_pengguna=self.asleb.nama, nim_nik=self.asleb.nim,
            email='asleb-term@std.trisakti.ac.id', password='rahasia123',
            no_hp=self.asleb.no_hp, alamat='Jakarta', fakultas='Teknologi Industri',
            prodi='Informatika', gender='perempuan', role='asisten_lab', is_verified=True,
        )
        session = self.client.session
        session['pengguna_id'] = laboran.pk
        session.save()

        response = self.client.post(reverse('asleb:asleb_end_membership', args=[self.asleb.pk]))

        self.assertRedirects(response, reverse('asleb:asleb_list'))
        akun_asleb.refresh_from_db()
        self.asleb.refresh_from_db()
        self.assertEqual(akun_asleb.role, 'mahasiswa')
        self.assertEqual(self.asleb.status, 'nonaktif')

    def test_input_peserta_otomatis_mencocokkan_nim_dengan_akun(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Terhubung', nim_nik='0640020099',
            email='0640020099@std.trisakti.ac.id', password='rahasia123',
            no_hp='081200000199', alamat='Jakarta', fakultas='Teknologi Industri',
            prodi='Informatika', gender='laki_laki', role='mahasiswa', is_verified=True,
        )

        response = self.client.post(reverse('asleb:praktikum_peserta_create'), {
            'matkul': self.matkul.pk,
            'daftar_mahasiswa': '0640020099, Mahasiswa Terhubung\n0640020088, Belum Punya Akun',
        })

        self.assertEqual(response.status_code, 302)
        linked = PesertaPraktikum.objects.get(matkul=self.matkul, nim='0640020099')
        unlinked = PesertaPraktikum.objects.get(matkul=self.matkul, nim='0640020088')
        self.assertEqual(linked.pengguna, mahasiswa)
        self.assertIsNone(unlinked.pengguna)

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
        self.assertEqual(honor.metode_transfer, 'bni')
        self.assertEqual(honor.nomor_transfer, 'BNI 123456789')
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

    def test_honor_bank_lain_dipotong_dua_ribu_lima_ratus(self):
        honor = HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 4, 1),
            total_pertemuan=3,
            metode_transfer='bank_lain',
            nomor_transfer='1234567890',
        )

        self.assertEqual(honor.biaya_admin, 2500)
        self.assertEqual(honor.jumlah, 144500)

    def test_honor_ewallet_dipotong_seribu_lima_ratus(self):
        for metode in ('shopeepay', 'gopay', 'ovo'):
            honor = HonorAsleb.objects.create(
                asleb=self.asleb,
                bulan=date(2026, 5, 1),
                total_pertemuan=3,
                metode_transfer=metode,
                nomor_transfer='081234567890',
            )
            self.assertEqual(honor.biaya_admin, 1500)
            self.assertEqual(honor.jumlah, 145500)
            honor.delete()

    def test_honor_bni_dan_dana_tanpa_potongan(self):
        for metode in ('bni', 'dana'):
            honor = HonorAsleb.objects.create(
                asleb=self.asleb,
                bulan=date(2026, 6, 1),
                total_pertemuan=3,
                metode_transfer=metode,
                nomor_transfer='081234567890',
            )
            self.assertEqual(honor.biaya_admin, 0)
            self.assertEqual(honor.jumlah, 147000)
            honor.delete()

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
        self.assertContains(response, 'BNI 123456789')
        active_links = [link['title'] for link in response.context['sidebar_links'] if link['active']]
        self.assertEqual(active_links, ['Asisten Laboratorium'])
        asleb_group = next(link for link in response.context['sidebar_links'] if link['title'] == 'Asisten Laboratorium')
        self.assertEqual([child['title'] for child in asleb_group['children'] if child['active']], ['Rekap Honorarium'])

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
        jadwal = self.create_active_schedule()
        first_form = AbsensiAslebForm(
            data={
                'modul_praktikum': modul.pk,
                'pekerjaan': 'Membantu praktikum',
                'latitude': '-6.1680678',
                'longitude': '106.7916257',
                'gps_accuracy': '10',
            },
            files={
                'bukti_foto': self.make_camera_photo('foto-1.png'),
                'bukti_video': SimpleUploadedFile('video-1.mp4', b'video 1', content_type='video/mp4'),
            },
            asleb=self.asleb,
            jadwal=jadwal,
        )
        self.assertTrue(first_form.is_valid(), first_form.errors)
        first_absensi = first_form.save(commit=False)
        first_absensi.asleb = self.asleb
        first_absensi.save()

        second_form = AbsensiAslebForm(
            data={
                'modul_praktikum': modul.pk,
                'pekerjaan': 'Membantu praktikum',
                'latitude': '-6.1680678',
                'longitude': '106.7916257',
                'gps_accuracy': '10',
            },
            files={
                'bukti_foto': self.make_camera_photo('foto-2.png'),
                'bukti_video': SimpleUploadedFile('video-2.mp4', b'video 2', content_type='video/mp4'),
            },
            asleb=self.asleb,
            jadwal=jadwal,
        )

        self.assertFalse(second_form.is_valid())
        self.assertIn('modul_praktikum', second_form.errors)

    @skipUnless(ENABLE_CAMERA_LOCATION_CAPTURE, 'Validasi radius lokasi sedang dinonaktifkan sementara.')
    def test_absensi_ditolak_jika_di_luar_radius_kampus(self):
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
            nomor=2,
            judul='Linked List',
            file=SimpleUploadedFile('modul-2.pdf', b'isi modul', content_type='application/pdf'),
        )
        form = AbsensiAslebForm(
            data={
                'modul_praktikum': modul.pk,
                'pekerjaan': 'Membantu praktikum',
                'latitude': '-6.2000000',
                'longitude': '106.8000000',
                'gps_accuracy': '10',
            },
            files={
                'bukti_foto': self.make_camera_photo(),
                'bukti_video': SimpleUploadedFile('video.mp4', b'video', content_type='video/mp4'),
            },
            asleb=self.asleb,
            jadwal=self.create_active_schedule(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn('radius 150 meter', str(form.non_field_errors()))

    def test_absensi_menerima_mime_video_dengan_codec_dari_browser(self):
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
            nomor=3,
            judul='Tree dan Graph',
            file=SimpleUploadedFile('modul-3.pdf', b'isi modul', content_type='application/pdf'),
        )
        form = AbsensiAslebForm(
            data={
                'modul_praktikum': modul.pk,
                'pekerjaan': 'Membantu praktikum',
                'latitude': '-6.1680678',
                'longitude': '106.7916257',
                'gps_accuracy': '10',
            },
            files={
                'bukti_foto': self.make_camera_photo('foto-browser.png'),
                'bukti_video': SimpleUploadedFile(
                    'video-browser.webm',
                    b'video browser',
                    content_type='video/webm;codecs=vp9,opus',
                ),
            },
            asleb=self.asleb,
            jadwal=self.create_active_schedule(),
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_absensi_menolak_absensi_kedua_di_hari_yang_sama_meski_jadwal_berubah(self):
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
        modul_pertama = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=4,
            judul='Sorting',
            file=SimpleUploadedFile('modul-4.pdf', b'isi modul 4', content_type='application/pdf'),
        )
        modul_kedua = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=5,
            judul='Searching',
            file=SimpleUploadedFile('modul-5.pdf', b'isi modul 5', content_type='application/pdf'),
        )
        jadwal_awal = self.create_active_schedule()
        AbsensiAsleb.objects.create(
            asleb=self.asleb,
            jadwal=jadwal_awal,
            modul_praktikum=modul_pertama,
            tanggal_praktikum=timezone.localdate(),
            modul=modul_pertama.nomor,
            materi_praktikum=modul_pertama.judul,
            file_modul=modul_pertama.file,
            bukti_foto=self.make_camera_photo('foto-awal.png'),
            bukti_video=SimpleUploadedFile('video-awal.mp4', b'video awal', content_type='video/mp4'),
            latitude='-6.1680678',
            longitude='106.7916257',
            jarak_lokasi_meter=10,
        )
        jadwal_diubah = JadwalPraktikum.objects.create(
            mata_kuliah=str(self.matkul),
            kelas=self.matkul.kelas,
            ruangan=jadwal_awal.ruangan,
            pengampu=self.matkul.dosen,
            hari='senin',
            waktu_mulai='13:00',
            waktu_selesai='15:00',
            status=JadwalPraktikum.STATUS_DITERIMA,
        )
        form = AbsensiAslebForm(
            data={
                'modul_praktikum': modul_kedua.pk,
                'pekerjaan': 'Membantu praktikum sesi kedua',
                'latitude': '-6.1680678',
                'longitude': '106.7916257',
                'gps_accuracy': '10',
            },
            files={
                'bukti_foto': self.make_camera_photo('foto-kedua.png'),
                'bukti_video': SimpleUploadedFile('video-kedua.mp4', b'video kedua', content_type='video/mp4'),
            },
            asleb=self.asleb,
            jadwal=jadwal_diubah,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('sudah melakukan absensi', str(form.non_field_errors()))

    def test_pengingat_email_maksimal_tiga_kali(self):
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
        self.create_active_schedule()
        reminder_times = [
            timezone.make_aware(datetime(2026, 6, 29, 9, 31)),
            timezone.make_aware(datetime(2026, 6, 29, 10, 7)),
            timezone.make_aware(datetime(2026, 6, 29, 10, 43)),
            timezone.make_aware(datetime(2026, 6, 29, 10, 50)),
        ]

        for current_time in reminder_times:
            with patch(
                'apps.asleb.management.commands.send_absensi_reminders.timezone.localtime',
                return_value=current_time,
            ):
                call_command('send_absensi_reminders')

        self.assertEqual(len(mail.outbox), 3)
        self.assertIn('1/3', mail.outbox[0].subject)
        self.assertIn('3/3', mail.outbox[2].subject)

    def create_active_schedule(self):
        room = RuanganLab.objects.filter(aktif=True).first()
        return JadwalPraktikum.objects.create(
            mata_kuliah=str(self.matkul),
            kelas=self.matkul.kelas,
            ruangan=room,
            pengampu=self.matkul.dosen,
            hari='senin',
            waktu_mulai='09:00',
            waktu_selesai='11:00',
            status=JadwalPraktikum.STATUS_DITERIMA,
        )

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
                metode_rekening='bni',
                rekening='BNI 123456789',
                status='digenerate',
            )
