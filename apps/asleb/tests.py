import base64
import shutil
import tempfile
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from unittest import skipUnless
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from reportlab.lib.enums import TA_RIGHT

from apps.pendaftaran_asleb.models import (
    AslabAssignment,
    AslabReplacement,
    AslabSlot,
    MataKuliahAsleb,
    PendaftaranAsleb,
    PeriodeAsleb,
)
from apps.pendaftaran_asleb.services import deactivate_asleb_membership, get_asleb_experience, sync_expired_asleb_periods
from apps.kalender.models import Notifikasi
from apps.pengguna.models import PengalamanPengguna, Pengguna
from apps.jadwal.models import JadwalPraktikum, PermintaanPerubahanJadwal
from apps.ruangan.models import RuanganLab

from .forms import (
    AbsensiAslebForm,
    ENABLE_CAMERA_LOCATION_CAPTURE,
    TugasLaporanPraktikumForm,
    get_asleb_matkul,
)
from .models import (
    AbsensiAsleb,
    AbsensiMasukAsleb,
    Asleb,
    HasilPraktikumMahasiswa,
    HonorAsleb,
    HonorReassignment,
    ModulPraktikum,
    PengaturanAbsensiAsleb,
    PengingatAbsensiAsleb,
    PengumpulanLaporanPraktikum,
    PesertaPraktikum,
    SuratHonorAsleb,
    TugasLaporanPraktikum,
)
from .views import get_praktikum_matkul_queryset
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
            nama_pengguna='Lab Laboran',
            nim_nik='LAB-ASLEB',
            email='laboran-asleb@example.com',
            password='rahasia123',
            no_hp='081234567800',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        self.matkul, _ = MataKuliahAsleb.objects.get_or_create(
            kode='SDA_TIF01_ABDUL',
            defaults={
                'nama': 'Struktur Data dan Algoritma',
                'dosen': 'Abdul Roohman',
                'kelas': 'TIF-01',
            },
        )
        self.test_room, _ = RuanganLab.objects.get_or_create(
            kode='LAB-ASLEB-TEST',
            defaults={'nama': 'Lab Asleb Test', 'kapasitas': 30, 'warna': 'teal', 'aktif': True},
        )
        session = self.client.session
        session['pengguna_id'] = pengguna.pk
        session.save()
        self.pengguna = pengguna

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

    def test_laboran_can_set_manual_aslab_level_and_honor_uses_it(self):
        response = self.client.post(
            reverse('asleb:asleb_update_level', args=[self.asleb.pk]),
            {'level_mode': 'manual', 'level_manual': 'senior'},
        )

        self.assertRedirects(response, reverse('asleb:asleb_detail', args=[self.asleb.pk]))
        self.asleb.refresh_from_db()
        self.assertEqual(self.asleb.level_mode, 'manual')
        self.assertEqual(self.asleb.level_manual, 'senior')
        self.assertEqual(self.asleb.level_efektif, 'senior')
        self.assertEqual(self.asleb.level_diatur_oleh, self.pengguna)
        self.assertIsNotNone(self.asleb.level_diatur_pada)
        self.assertEqual(get_asleb_experience(self.asleb.nim), ('senior', 2))

        honor = HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 7, 1),
            jumlah=Decimal('0'),
            total_pertemuan=1,
        )
        self.assertEqual(honor.level, 'senior')
        self.assertEqual(honor.honor_per_jam, 8000)

    def test_switching_back_to_automatic_ignores_manual_value(self):
        self.asleb.level_mode = 'manual'
        self.asleb.level_manual = 'senior'
        self.asleb.save(update_fields=['level_mode', 'level_manual'])

        response = self.client.post(
            reverse('asleb:asleb_update_level', args=[self.asleb.pk]),
            {'level_mode': 'otomatis', 'level_manual': 'senior'},
        )

        self.assertRedirects(response, reverse('asleb:asleb_detail', args=[self.asleb.pk]))
        self.asleb.refresh_from_db()
        self.assertEqual(self.asleb.level_mode, 'otomatis')
        self.assertEqual(self.asleb.level_manual, '')
        self.assertEqual(self.asleb.level_efektif, self.asleb.level_otomatis)

    def test_non_laboran_cannot_change_manual_aslab_level(self):
        self.pengguna.role = 'admin'
        self.pengguna.save(update_fields=['role'])

        response = self.client.post(
            reverse('asleb:asleb_update_level', args=[self.asleb.pk]),
            {'level_mode': 'manual', 'level_manual': 'senior'},
        )

        self.assertEqual(response.status_code, 302)
        self.asleb.refresh_from_db()
        self.assertEqual(self.asleb.level_mode, 'otomatis')
        self.assertEqual(self.asleb.level_manual, '')

    def test_aslab_with_operational_history_cannot_be_deleted(self):
        period = PeriodeAsleb.objects.create(
            tahun=2027, semester=1, mulai=date(2027, 1, 1), selesai=date(2027, 6, 30),
            pendaftaran_mulai=date(2026, 12, 1), pendaftaran_selesai=date(2026, 12, 31),
        )
        slot = AslabSlot.objects.create(
            periode=period, matkul=self.matkul, nomor=1, status=AslabSlot.STATUS_VACANT,
        )
        AslabAssignment.objects.create(
            slot=slot, asleb=self.asleb, mulai_pada=period.mulai,
            berakhir_pada=date(2027, 2, 1), status=AslabAssignment.STATUS_TERMINATED,
        )

        response = self.client.post(reverse('asleb:asleb_delete', args=[self.asleb.pk]))

        self.assertRedirects(response, reverse('asleb:asleb_detail', args=[self.asleb.pk]))
        self.assertTrue(Asleb.objects.filter(pk=self.asleb.pk).exists())

    def test_unused_mistaken_aslab_record_can_be_deleted(self):
        response = self.client.post(reverse('asleb:asleb_delete', args=[self.asleb.pk]))

        self.assertRedirects(response, reverse('asleb:asleb_list'))
        self.assertFalse(Asleb.objects.filter(pk=self.asleb.pk).exists())

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

    def create_active_assignment(self):
        period = PeriodeAsleb.objects.create(
            tahun=2026, semester=2, mulai=date(2026, 7, 1), selesai=date(2026, 12, 31),
            pendaftaran_mulai=date(2026, 7, 1), pendaftaran_selesai=date(2026, 7, 30),
        )
        slot = AslabSlot.objects.create(periode=period, matkul=self.matkul, nomor=1)
        self.asleb.periode_aktif = period
        self.asleb.save(update_fields=['periode_aktif', 'diperbarui_pada'])
        return AslabAssignment.objects.create(
            slot=slot, asleb=self.asleb, mulai_pada=date(2026, 7, 1),
            status=AslabAssignment.STATUS_ACTIVE,
        )

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

    def test_daftar_absensi_modul_memakai_preview_inline(self):
        modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=9,
            judul='Tree',
            file=SimpleUploadedFile('modul-9.pdf', b'%PDF-1.4\n%%EOF', content_type='application/pdf'),
        )
        AbsensiAsleb.objects.create(
            asleb=self.asleb,
            jadwal=self.create_active_schedule(),
            modul_praktikum=modul,
            tanggal_praktikum=date(2026, 6, 24),
            modul=9,
            materi_praktikum='Tree',
            pekerjaan='Praktikum struktur tree',
            file_modul=SimpleUploadedFile('modul-lama.pdf', b'isi modul', content_type='application/pdf'),
        )

        response = self.client.get(reverse('asleb:absensi_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-open-inline-modul-preview')
        self.assertContains(response, reverse('asleb:modul_preview', args=[modul.pk]))
        self.assertContains(response, reverse('asleb:modul_viewer', args=[modul.pk]))
        self.assertContains(response, 'core/vendor/pdfjs/pdf.min.mjs')
        self.assertContains(response, 'renderPdfPages(button.dataset.previewUrl)')
        self.assertContains(response, reverse('asleb:modul_download', args=[modul.pk]))
        self.assertNotContains(response, f'href="{reverse("asleb:modul_download", args=[modul.pk])}">Unduh modul</a>')

    def test_preview_modul_dikirim_inline_dan_download_tetap_attachment(self):
        modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=10,
            judul='Graph',
            file=SimpleUploadedFile('modul-10.pdf', b'%PDF-1.4\n%%EOF', content_type='application/pdf'),
        )

        preview = self.client.get(reverse('asleb:modul_preview', args=[modul.pk]))
        download = self.client.get(reverse('asleb:modul_download', args=[modul.pk]))

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview['Content-Type'], 'application/pdf')
        self.assertIn('inline', preview.get('Content-Disposition', ''))
        self.assertIn('attachment', download.get('Content-Disposition', ''))

    def test_mahasiswa_hanya_dapat_membuka_modul_matkul_yang_diikuti(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Peserta Modul',
            nim_nik='0640020771',
            email='peserta-modul@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081200000771',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
            is_verified=True,
        )
        modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=11,
            judul='Modul Peserta',
            file=SimpleUploadedFile('modul-peserta.pdf', b'%PDF-1.4\n%%EOF', content_type='application/pdf'),
        )
        PesertaPraktikum.objects.create(
            matkul=self.matkul,
            pengguna=mahasiswa,
            nim=mahasiswa.nim_nik,
            nama=mahasiswa.nama_pengguna,
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('asleb:modul_preview', args=[modul.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        PesertaPraktikum.objects.filter(pengguna=mahasiswa).update(aktif=False)
        denied = self.client.get(reverse('asleb:modul_preview', args=[modul.pk]))
        self.assertRedirects(
            denied,
            reverse('asleb:absensi_list'),
            fetch_redirect_response=False,
        )

    def test_asisten_senior_dapat_membuka_dan_absen_modul_dari_dua_penugasan(self):
        pengguna_aslab = Pengguna.objects.create(
            nama_pengguna='Aslab Senior',
            nim_nik=self.asleb.nim,
            email='aslab-senior@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081200000772',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
            is_verified=True,
        )
        first_assignment = self.create_active_assignment()
        second_matkul = MataKuliahAsleb.objects.create(
            kode='SENIOR_SECOND_COURSE',
            kode_mk='SSC01',
            nama='Keamanan Aplikasi',
            dosen='Dosen Keamanan',
            kelas='TIF-02',
        )
        second_slot = AslabSlot.objects.create(
            periode=first_assignment.slot.periode,
            matkul=second_matkul,
            nomor=1,
        )
        AslabAssignment.objects.create(
            slot=second_slot,
            asleb=self.asleb,
            mulai_pada=first_assignment.mulai_pada,
            status=AslabAssignment.STATUS_ACTIVE,
        )
        first_modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=12,
            judul='Modul Pertama',
            file=SimpleUploadedFile('senior-1.pdf', b'%PDF-1.4\n%%EOF', content_type='application/pdf'),
        )
        second_modul = ModulPraktikum.objects.create(
            matkul=second_matkul,
            nomor=1,
            judul='Modul Kedua',
            file=SimpleUploadedFile('senior-2.pdf', b'%PDF-1.4\n%%EOF', content_type='application/pdf'),
        )
        session = self.client.session
        session['pengguna_id'] = pengguna_aslab.pk
        session.save()

        first_response = self.client.get(reverse('asleb:modul_preview', args=[first_modul.pk]))
        second_response = self.client.get(reverse('asleb:modul_preview', args=[second_modul.pk]))
        second_schedule = JadwalPraktikum.objects.create(
            mata_kuliah=str(second_matkul),
            kelas=second_matkul.kelas,
            ruangan=self.test_room,
            pengampu=second_matkul.dosen,
            hari='senin',
            waktu_mulai='08:00',
            waktu_selesai='10:00',
            status=JadwalPraktikum.STATUS_DITERIMA,
        )
        form = AbsensiAslebForm(asleb=self.asleb, jadwal=second_schedule)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertIn(second_modul, form.fields['modul_praktikum'].queryset)
        self.assertNotIn(first_modul, form.fields['modul_praktikum'].queryset)

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
            'file': SimpleUploadedFile('modul-sda.pdf', b'%PDF-1.4\n%%EOF', content_type='application/pdf'),
        })

        self.assertRedirects(response, reverse('asleb:absensi_list'))
        self.assertTrue(ModulPraktikum.objects.filter(matkul=self.matkul, nomor=1, diunggah_oleh=laboran).exists())

    def test_laboran_tidak_dapat_mengunggah_file_palsu_bernama_pdf(self):
        laboran = Pengguna.objects.create(
            nama_pengguna='Laboran File Aman',
            nim_nik='1000000097',
            email='laboran-file-aman@example.com',
            password='rahasia123',
            role='laboran',
        )
        session = self.client.session
        session['pengguna_id'] = laboran.pk
        session.save()

        response = self.client.post(reverse('asleb:modul_create'), {
            'matkul': self.matkul.pk,
            'nomor': 1,
            'judul': 'File Palsu',
            'file': SimpleUploadedFile(
                'modul-palsu.pdf',
                b'<html><script>alert(1)</script></html>',
                content_type='application/pdf',
            ),
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Isi file bukan PDF yang valid.')
        self.assertFalse(ModulPraktikum.objects.filter(matkul=self.matkul, nomor=1).exists())

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

    def test_asisten_lab_hanya_melihat_matkul_aslab_yang_masih_aktif(self):
        matkul_lama = MataKuliahAsleb.objects.create(
            kode='PM_TEST_LAMA',
            kode_mk='PM001',
            nama='Pemrograman Mobile',
            dosen='Dosen Mobile',
            kelas='SI-01',
            aktif=True,
        )
        matkul_baru = MataKuliahAsleb.objects.create(
            kode='PW_TEST_BARU',
            kode_mk='PW001',
            nama='Pemrograman Web',
            dosen='Dosen Web',
            kelas='SI-01',
            aktif=True,
        )
        pengguna_aslab = Pengguna.objects.create(
            nama_pengguna='Aslab Aktif',
            nim_nik='0640020098',
            email='aslab-aktif@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567801',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='asisten_lab',
            is_verified=True,
        )
        asleb_aktif = Asleb.objects.create(
            nama='Aslab Aktif',
            nim=pengguna_aslab.nim_nik,
            no_hp=pengguna_aslab.no_hp,
            email=pengguna_aslab.email,
            program_studi=pengguna_aslab.prodi,
            matkul=str(matkul_baru),
            semester=4,
            status='aktif',
            tanggal_bergabung=date(2026, 7, 10),
        )

        matkul_queryset = get_praktikum_matkul_queryset(pengguna_aslab)

        self.assertEqual(list(matkul_queryset), [matkul_baru])
        self.assertEqual(get_asleb_matkul(asleb_aktif), matkul_baru)

    def test_laboran_tidak_bisa_mengeluarkan_asleb_tanpa_alasan(self):
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

        response = self.client.post(
            reverse('asleb:asleb_end_membership', args=[self.asleb.pk]),
            {'alasan_pengeluaran': ''},
            follow=True,
        )

        akun_asleb.refresh_from_db()
        self.asleb.refresh_from_db()
        self.assertContains(response, 'Alasan pengeluaran Aslab wajib diisi')
        self.assertEqual(akun_asleb.role, 'asisten_lab')
        self.assertEqual(self.asleb.status, 'aktif')
        self.assertFalse(PengalamanPengguna.objects.filter(pengguna=akun_asleb).exists())

    @patch('apps.asleb.views.timezone.localdate', return_value=date(2026, 10, 15))
    def test_laboran_dapat_mengeluarkan_asleb_dengan_alasan_tanpa_masuk_pengalaman(self, _localdate):
        laboran = Pengguna.objects.create(
            nama_pengguna='Laboran Terminasi', nim_nik='LAB-TERM-2',
            email='laboran-term-2@trisakti.ac.id', password='rahasia123',
            no_hp='081200000098', alamat='Jakarta', fakultas='Teknologi Industri',
            prodi='Informatika', gender='laki_laki', role='laboran', is_verified=True,
        )
        akun_asleb = Pengguna.objects.create(
            nama_pengguna=self.asleb.nama, nim_nik=self.asleb.nim,
            email='asleb-term-2@std.trisakti.ac.id', password='rahasia123',
            no_hp=self.asleb.no_hp, alamat='Jakarta', fakultas='Teknologi Industri',
            prodi='Informatika', gender='perempuan', role='asisten_lab', is_verified=True,
        )
        session = self.client.session
        session['pengguna_id'] = laboran.pk
        session.save()
        assignment = self.create_active_assignment()

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('asleb:asleb_end_membership', args=[self.asleb.pk]),
                {'alasan_pengeluaran': 'Pelanggaran aturan laboratorium.'},
                follow=True,
            )

        akun_asleb.refresh_from_db()
        self.asleb.refresh_from_db()
        self.assertContains(response, 'notifikasi telah dikirim')
        self.assertEqual(akun_asleb.role, 'mahasiswa')
        self.assertEqual(self.asleb.status, 'nonaktif')
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, AslabAssignment.STATUS_TERMINATED)
        self.assertTrue(AslabReplacement.objects.filter(outgoing_assignment=assignment).exists())
        self.assertFalse(PengalamanPengguna.objects.filter(pengguna=akun_asleb).exists())
        self.assertTrue(Notifikasi.objects.filter(
            pengguna=akun_asleb,
            source_key__startswith='aslab-replacement:',
            source_key__endswith=':assignment-ended',
        ).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Masa Tugas Aslab Diakhiri', mail.outbox[0].subject)

    @patch('apps.asleb.views.timezone.localdate', return_value=date(2026, 10, 15))
    @patch('apps.asleb.views.end_single_active_assignment_for_replacement')
    def test_end_membership_delegates_to_replacement_service(self, end_assignment, _localdate):
        assignment = self.create_active_assignment()
        end_assignment.return_value = AslabReplacement(
            outgoing_assignment=assignment, slot=assignment.slot,
        )

        response = self.client.post(
            reverse('asleb:asleb_end_membership', args=[self.asleb.pk]),
            {'alasan_pengeluaran': 'Pelanggaran aturan.'},
        )

        self.assertRedirects(response, reverse('asleb:asleb_list'))
        end_assignment.assert_called_once_with(
            asleb_id=self.asleb.pk,
            actor=self.pengguna,
            reason_type='dismissal',
            reason='Pelanggaran aturan.',
            effective_date=date(2026, 10, 15),
        )

    def test_end_membership_legacy_without_assignment_is_safe(self):
        response = self.client.post(
            reverse('asleb:asleb_end_membership', args=[self.asleb.pk]),
            {'alasan_pengeluaran': 'Pelanggaran aturan.'},
            follow=True,
        )

        self.asleb.refresh_from_db()
        self.assertContains(response, 'belum memiliki penugasan aktif')
        self.assertEqual(self.asleb.status, 'aktif')
        self.assertFalse(AslabReplacement.objects.exists())

    def test_end_membership_with_multiple_active_assignments_is_safe(self):
        first_assignment = self.create_active_assignment()
        other_course = MataKuliahAsleb.objects.create(
            kode='AMBIGU_TIF01', kode_mk='AMB01', nama='Assignment Ambigu',
            dosen='Dosen Test', kelas='TIF-02',
        )
        other_slot = AslabSlot.objects.create(
            periode=first_assignment.slot.periode, matkul=other_course, nomor=1,
        )
        second_assignment = AslabAssignment.objects.create(
            slot=other_slot, asleb=self.asleb, mulai_pada=date(2026, 7, 1),
            status=AslabAssignment.STATUS_ACTIVE,
        )

        response = self.client.post(
            reverse('asleb:asleb_end_membership', args=[self.asleb.pk]),
            {'alasan_pengeluaran': 'Pelanggaran aturan.'},
            follow=True,
        )

        first_assignment.refresh_from_db()
        second_assignment.refresh_from_db()
        self.assertContains(response, 'pilih mata kuliah/slot tertentu')
        self.assertEqual(first_assignment.status, AslabAssignment.STATUS_ACTIVE)
        self.assertEqual(second_assignment.status, AslabAssignment.STATUS_ACTIVE)
        self.assertFalse(AslabReplacement.objects.exists())

    @patch('apps.asleb.views.timezone.localdate', return_value=date(2026, 10, 15))
    @patch('apps.asleb.views.end_single_active_assignment_for_replacement')
    def test_end_membership_does_not_send_global_notification_when_access_remains(
        self, end_assignment, _localdate,
    ):
        assignment = self.create_active_assignment()
        end_assignment.return_value = AslabReplacement(
            outgoing_assignment=assignment, slot=assignment.slot,
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('asleb:asleb_end_membership', args=[self.asleb.pk]),
                {'alasan_pengeluaran': 'Mengakhiri satu penugasan.'},
                follow=True,
            )

        self.assertContains(response, 'Satu penugasan Aslab')
        self.assertNotContains(response, 'notifikasi telah dikirim')
        self.assertFalse(Notifikasi.objects.filter(pengguna__nim_nik=self.asleb.nim).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_data_aslab_tidak_menampilkan_tombol_edit_dan_hapus(self):
        response = self.client.get(reverse('asleb:asleb_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('asleb:asleb_detail', args=[self.asleb.pk]))
        self.assertNotContains(response, reverse('asleb:asleb_update', args=[self.asleb.pk]))
        self.assertNotContains(response, reverse('asleb:asleb_delete', args=[self.asleb.pk]))
        self.assertNotContains(response, '<span>Edit</span>', html=False)
        self.assertNotContains(response, '<span>Hapus</span>', html=False)

    def test_detail_aslab_tidak_menampilkan_tombol_edit(self):
        response = self.client.get(reverse('asleb:asleb_detail', args=[self.asleb.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('asleb:asleb_update', args=[self.asleb.pk]))
        self.assertNotContains(response, '<span>Edit</span>', html=False)

    def test_input_peserta_otomatis_mencocokkan_nim_dengan_akun(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Terhubung', nim_nik='0640020099',
            email='0640020099@std.trisakti.ac.id', password='rahasia123',
            no_hp='081200000199', alamat='Jakarta', fakultas='Teknologi Industri',
            prodi='Informatika', gender='laki_laki', role='mahasiswa', is_verified=True,
        )

        response = self.client.post(reverse('asleb:praktikum_peserta_create'), {
            'metode_input': 'manual',
            'matkul': self.matkul.pk,
            'daftar_mahasiswa': '0640020099, Mahasiswa Terhubung\n0640020088, Belum Punya Akun',
        })

        self.assertEqual(response.status_code, 302)
        linked = PesertaPraktikum.objects.get(matkul=self.matkul, nim='0640020099')
        unlinked = PesertaPraktikum.objects.get(matkul=self.matkul, nim='0640020088')
        self.assertEqual(linked.pengguna, mahasiswa)
        self.assertIsNone(unlinked.pengguna)

    def test_import_peserta_praktikum_dari_csv(self):
        csv_file = SimpleUploadedFile(
            'peserta.csv',
            b'No,Student Name,Student ID\n1,NAUFAL FAHREZI MAULANA,64102500001\n2,RAJA PANGLIMA ISLAM,64102500004\n',
            content_type='text/csv',
        )

        response = self.client.post(
            reverse('asleb:praktikum_peserta_create'),
            {
                'metode_input': 'csv',
                'matkul': self.matkul.pk,
                'file_csv': csv_file,
            },
        )

        self.assertRedirects(response, f'{reverse("asleb:praktikum_mahasiswa_list")}?matkul={self.matkul.pk}')
        self.assertTrue(PesertaPraktikum.objects.filter(matkul=self.matkul, nim='64102500001', nama='NAUFAL FAHREZI MAULANA').exists())
        self.assertTrue(PesertaPraktikum.objects.filter(matkul=self.matkul, nim='64102500004', nama='RAJA PANGLIMA ISLAM').exists())

    def test_daftar_peserta_praktikum_muncul_dalam_modal(self):
        peserta = PesertaPraktikum.objects.create(matkul=self.matkul, nim='0640020099', nama='Mahasiswa Modal')

        response = self.client.get(reverse('asleb:praktikum_mahasiswa_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-participant-modal-open')
        self.assertContains(response, f'id="participants-{self.matkul.pk}"')
        self.assertContains(response, 'data-participant-search')
        self.assertContains(response, 'data-select-all')
        self.assertContains(response, 'Hapus Terpilih')
        self.assertContains(response, 'document.body.appendChild(modal)')
        self.assertContains(response, 'html[data-theme="dark"] .participant-modal')
        self.assertContains(response, 'participant-table-action')
        self.assertContains(response, reverse('asleb:praktikum_peserta_update', args=[peserta.pk]))

    def test_laboran_dapat_menghapus_banyak_peserta_praktikum(self):
        peserta_pertama = PesertaPraktikum.objects.create(matkul=self.matkul, nim='0640020099', nama='Mahasiswa Satu')
        peserta_kedua = PesertaPraktikum.objects.create(matkul=self.matkul, nim='0640020088', nama='Mahasiswa Dua')

        response = self.client.post(reverse('asleb:praktikum_peserta_bulk_delete'), {
            'matkul_id': self.matkul.pk,
            'peserta_ids': [peserta_pertama.pk, peserta_kedua.pk],
        })

        self.assertRedirects(response, f'{reverse("asleb:praktikum_mahasiswa_list")}?matkul={self.matkul.pk}')
        self.assertFalse(PesertaPraktikum.objects.filter(pk__in=[peserta_pertama.pk, peserta_kedua.pk]).exists())

    def test_laboran_dapat_mengedit_peserta_praktikum(self):
        peserta = PesertaPraktikum.objects.create(matkul=self.matkul, nim='0640020099', nama='Mahasiswa Lama')

        response = self.client.post(reverse('asleb:praktikum_peserta_update', args=[peserta.pk]), {
            'matkul': self.matkul.pk,
            'nim': '0640020098',
            'nama': 'Mahasiswa Baru',
            'aktif': 'on',
        })

        self.assertRedirects(response, f'{reverse("asleb:praktikum_mahasiswa_list")}?matkul={self.matkul.pk}')
        peserta.refresh_from_db()
        self.assertEqual(peserta.nim, '0640020098')
        self.assertEqual(peserta.nama, 'Mahasiswa Baru')

    def test_export_nilai_praktikum_excel(self):
        peserta = PesertaPraktikum.objects.create(matkul=self.matkul, nim='0640020099', nama='Mahasiswa Nilai')
        modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=1,
            judul='Pengenalan',
            file=SimpleUploadedFile('modul.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        HasilPraktikumMahasiswa.objects.create(
            peserta=peserta,
            modul=modul,
            tanggal_praktikum=date(2026, 7, 1),
            status_absensi='hadir',
            nilai_realtime=80,
            nilai_laporan=90,
            catatan='Baik',
            dicatat_oleh=self.pengguna,
        )
        modul_2 = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=2,
            judul='Array',
            file=SimpleUploadedFile('modul-2.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        HasilPraktikumMahasiswa.objects.create(
            peserta=peserta,
            modul=modul_2,
            tanggal_praktikum=date(2026, 7, 8),
            status_absensi='hadir',
            nilai_realtime=90,
            nilai_laporan=100,
            dicatat_oleh=self.pengguna,
        )

        response = self.client.get(reverse('asleb:praktikum_nilai_export'), {'matkul': self.matkul.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertTrue(response.content.startswith(b'PK'))
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), 1)
            workbook_bytes = archive.read(names[0])
        with zipfile.ZipFile(BytesIO(workbook_bytes)) as workbook:
            sheet = workbook.read('xl/worksheets/sheet1.xml').decode()
        self.assertIn('Modul 1', sheet)
        self.assertIn('Modul 2', sheet)
        self.assertIn('Total Nilai', sheet)
        self.assertIn('Rata-rata Nilai', sheet)
        self.assertIn('85.00', sheet)
        self.assertIn('95.00', sheet)
        self.assertIn('180.00', sheet)
        self.assertIn('90.00', sheet)

    def test_export_nilai_semua_matkul_dipisah_dalam_zip(self):
        matkul_lain = MataKuliahAsleb.objects.create(
            nama='Pemrograman Web',
            kode='IF202',
            kelas='TIF-02',
            dosen='Bu Dosen',
        )
        peserta_1 = PesertaPraktikum.objects.create(matkul=self.matkul, nim='0640020099', nama='Mahasiswa Satu')
        peserta_2 = PesertaPraktikum.objects.create(matkul=matkul_lain, nim='0640020100', nama='Mahasiswa Dua')
        modul_1 = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=1,
            judul='Pengenalan',
            file=SimpleUploadedFile('modul-1.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        modul_2 = ModulPraktikum.objects.create(
            matkul=matkul_lain,
            nomor=1,
            judul='HTML',
            file=SimpleUploadedFile('modul-web.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        HasilPraktikumMahasiswa.objects.create(peserta=peserta_1, modul=modul_1, nilai_realtime=80, nilai_laporan=90)
        HasilPraktikumMahasiswa.objects.create(peserta=peserta_2, modul=modul_2, nilai_realtime=70, nilai_laporan=80)

        response = self.client.get(reverse('asleb:praktikum_nilai_export'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            names = archive.namelist()
        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(names), 2)
        self.assertTrue(all(name.endswith('.xlsx') for name in names))

    def test_hapus_semua_peserta_mengosongkan_daftar_dan_menyimpan_riwayat_nilai(self):
        peserta_dengan_nilai = PesertaPraktikum.objects.create(matkul=self.matkul, nim='0640020099', nama='Mahasiswa Nilai')
        peserta_tanpa_nilai = PesertaPraktikum.objects.create(matkul=self.matkul, nim='0640020100', nama='Mahasiswa Kosong')
        modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=1,
            judul='Pengenalan',
            file=SimpleUploadedFile('modul.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        HasilPraktikumMahasiswa.objects.create(peserta=peserta_dengan_nilai, modul=modul, nilai_realtime=80, nilai_laporan=90)

        response = self.client.post(reverse('asleb:praktikum_peserta_delete_all', args=[self.matkul.pk]))

        self.assertRedirects(response, f'{reverse("asleb:praktikum_mahasiswa_list")}?matkul={self.matkul.pk}')
        peserta_dengan_nilai.refresh_from_db()
        self.assertFalse(peserta_dengan_nilai.aktif)
        self.assertFalse(PesertaPraktikum.objects.filter(pk=peserta_tanpa_nilai.pk).exists())
        self.assertTrue(HasilPraktikumMahasiswa.objects.filter(peserta=peserta_dengan_nilai).exists())

    def test_input_nilai_menghitung_rata_rata_realtime_dan_laporan(self):
        peserta = PesertaPraktikum.objects.create(matkul=self.matkul, nim='0640020099', nama='Mahasiswa Nilai')
        modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=1,
            judul='Pengenalan',
            file=SimpleUploadedFile('modul.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )

        response = self.client.post(
            reverse('asleb:praktikum_nilai', args=[self.matkul.pk, modul.pk]),
            {
                'tanggal_praktikum': '2026-07-01',
                f'peserta-{peserta.pk}-status_absensi': 'hadir',
                f'peserta-{peserta.pk}-nilai_realtime': '80',
                f'peserta-{peserta.pk}-nilai_laporan': '90',
                f'peserta-{peserta.pk}-catatan': 'Stabil',
            },
        )

        self.assertRedirects(response, reverse('asleb:praktikum_nilai', args=[self.matkul.pk, modul.pk]))
        hasil = HasilPraktikumMahasiswa.objects.get(peserta=peserta, modul=modul)
        self.assertEqual(hasil.nilai_realtime, 80)
        self.assertEqual(hasil.nilai_laporan, 90)
        self.assertEqual(hasil.nilai, 85)

    def test_peserta_dinonaktifkan_saat_periode_berakhir_dan_nilai_tetap_terhubung(self):
        today = timezone.localdate()
        period = PeriodeAsleb.objects.create(
            tahun=today.year,
            semester=1 if today.month <= 6 else 2,
            mulai=today - timedelta(days=120),
            selesai=today - timedelta(days=1),
            pendaftaran_mulai=today - timedelta(days=150),
            pendaftaran_selesai=today - timedelta(days=130),
        )
        self.asleb.periode_aktif = period
        self.asleb.status = 'aktif'
        self.asleb.matkul = str(self.matkul)
        self.asleb.save(update_fields=['periode_aktif', 'status', 'matkul'])
        Pengguna.objects.create(
            nama_pengguna=self.asleb.nama,
            nim_nik=self.asleb.nim,
            email='asleb-expired@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567899',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
        )
        peserta = PesertaPraktikum.objects.create(matkul=self.matkul, nim='0640020099', nama='Mahasiswa Nilai')
        modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=2,
            judul='Percabangan',
            file=SimpleUploadedFile('modul2.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        hasil = HasilPraktikumMahasiswa.objects.create(
            peserta=peserta,
            modul=modul,
            tanggal_praktikum=date(2026, 7, 2),
            status_absensi='hadir',
            nilai=90,
        )

        sync_expired_asleb_periods(today)

        self.assertTrue(PesertaPraktikum.objects.filter(pk=peserta.pk, aktif=False).exists())
        hasil.refresh_from_db()
        self.assertEqual(hasil.peserta, peserta)
        self.assertEqual(hasil.peserta_nim, '0640020099')
        self.assertEqual(hasil.peserta_nama, 'Mahasiswa Nilai')
        self.assertEqual(hasil.nilai, 90)

    def test_periode_berakhir_memfinalisasi_operasional_tanpa_menghapus_histori(self):
        today = timezone.localdate()
        period = PeriodeAsleb.objects.create(
            tahun=today.year,
            semester=1 if today.month <= 6 else 2,
            mulai=today - timedelta(days=120),
            selesai=today - timedelta(days=1),
            pendaftaran_mulai=today - timedelta(days=150),
            pendaftaran_selesai=today - timedelta(days=130),
        )
        akun_aslab = Pengguna.objects.create(
            nama_pengguna=self.asleb.nama,
            nim_nik=self.asleb.nim,
            email='cleanup-aslab@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567899',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
        )
        self.asleb.periode_aktif = period
        self.asleb.status = 'aktif'
        self.asleb.matkul = str(self.matkul)
        self.asleb.save(update_fields=['periode_aktif', 'status', 'matkul'])
        PendaftaranAsleb.objects.create(
            nama=self.asleb.nama,
            nim=self.asleb.nim,
            no_hp=self.asleb.no_hp,
            email=self.asleb.email,
            program_studi=self.asleb.program_studi,
            semester=self.asleb.semester,
            matkul=self.matkul,
            periode=period,
            status='digenerate',
        )
        peserta = PesertaPraktikum.objects.create(matkul=self.matkul, nim='0640020101', nama='Peserta Lama')
        modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=3,
            judul='Looping',
            file=SimpleUploadedFile('modul3.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        jadwal = JadwalPraktikum.objects.create(
            mata_kuliah=str(self.matkul),
            kelas=self.matkul.kelas,
            ruangan=self.test_room,
            pengampu=self.asleb.nama,
            hari='senin',
            waktu_mulai='08:00',
            waktu_selesai='09:00',
            status=JadwalPraktikum.STATUS_DITERIMA,
        )
        AbsensiAsleb.objects.create(
            asleb=self.asleb,
            jadwal=jadwal,
            modul_praktikum=modul,
            tanggal_praktikum=today - timedelta(days=5),
            modul=3,
            file_modul=SimpleUploadedFile('absensi-modul.pdf', b'%PDF-1.4', content_type='application/pdf'),
            bukti_video=SimpleUploadedFile('video.mp4', b'video', content_type='video/mp4'),
        )
        AbsensiMasukAsleb.objects.create(
            asleb=self.asleb,
            jadwal=jadwal,
            tanggal_absensi=today - timedelta(days=5),
            foto_absensi=SimpleUploadedFile('foto.jpg', b'foto', content_type='image/jpeg'),
        )
        PengingatAbsensiAsleb.objects.create(
            asleb=self.asleb,
            jadwal=jadwal,
            tanggal=today - timedelta(days=5),
            tahap=1,
        )
        tugas = TugasLaporanPraktikum.objects.create(
            judul='Laporan Modul 3',
            matkul=self.matkul,
            modul=modul,
            batas_pengumpulan=timezone.now() + timedelta(days=1),
            dibuat_oleh=akun_aslab,
        )
        PengumpulanLaporanPraktikum.objects.create(
            tugas=tugas,
            peserta=peserta,
            file_laporan=SimpleUploadedFile('laporan.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        change_request = PermintaanPerubahanJadwal.objects.create(
            jadwal=jadwal,
            matkul=self.matkul,
            ruangan=self.test_room,
            hari='selasa',
            waktu_mulai='10:00',
            waktu_selesai='11:00',
            diajukan_oleh=akun_aslab,
        )

        sync_expired_asleb_periods(today)

        akun_aslab.refresh_from_db()
        self.asleb.refresh_from_db()
        self.assertEqual(akun_aslab.role, 'mahasiswa')
        self.assertEqual(self.asleb.status, 'nonaktif')
        self.assertTrue(ModulPraktikum.objects.filter(pk=modul.pk).exists())
        self.assertTrue(PesertaPraktikum.objects.filter(pk=peserta.pk).exists())
        self.assertTrue(AbsensiAsleb.objects.filter(asleb=self.asleb).exists())
        self.assertTrue(AbsensiMasukAsleb.objects.filter(asleb=self.asleb).exists())
        self.assertTrue(PengingatAbsensiAsleb.objects.filter(asleb=self.asleb).exists())
        self.assertTrue(TugasLaporanPraktikum.objects.filter(pk=tugas.pk).exists())
        self.assertTrue(PengumpulanLaporanPraktikum.objects.filter(tugas=tugas).exists())
        self.assertTrue(JadwalPraktikum.objects.filter(pk=jadwal.pk).exists())
        self.assertTrue(PermintaanPerubahanJadwal.objects.filter(jadwal=jadwal).exists())
        tugas.refresh_from_db()
        peserta.refresh_from_db()
        change_request.refresh_from_db()
        self.assertFalse(tugas.aktif)
        self.assertFalse(peserta.aktif)
        self.assertEqual(change_request.status, 'ditolak')
        pengalaman = PengalamanPengguna.objects.get(pengguna=akun_aslab, otomatis=True)
        self.assertIn(str(self.matkul), pengalaman.deskripsi)

    def test_forced_deactivation_preserves_completed_operational_attendance(self):
        jadwal = JadwalPraktikum.objects.create(
            mata_kuliah=str(self.matkul),
            kelas=self.matkul.kelas,
            ruangan=self.test_room,
            pengampu=self.asleb.nama,
            hari='senin',
            waktu_mulai='08:00',
            waktu_selesai='09:00',
            status=JadwalPraktikum.STATUS_DITERIMA,
        )
        attendance = AbsensiMasukAsleb.objects.create(
            asleb=self.asleb,
            jadwal=jadwal,
            tanggal_absensi=timezone.localdate(),
            foto_absensi=SimpleUploadedFile('foto.jpg', b'foto', content_type='image/jpeg'),
        )
        original_asleb_id = attendance.asleb_id
        original_jadwal_id = attendance.jadwal_id
        original_date = attendance.tanggal_absensi
        original_status = attendance.status

        deactivate_asleb_membership(
            self.asleb,
            forced=True,
            reason='Mengundurkan diri',
            acted_by=self.pengguna,
        )

        attendance.refresh_from_db()
        self.assertEqual(attendance.asleb_id, original_asleb_id)
        self.assertEqual(attendance.jadwal_id, original_jadwal_id)
        self.assertEqual(attendance.tanggal_absensi, original_date)
        self.assertEqual(attendance.status, original_status)

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
        self.assertEqual(honor.nomor_transfer, '123456789')
        self.assertEqual(honor.nama_pemilik_transfer, 'Riwayat Asleb 3')

    def test_asisten_lab_hanya_melihat_honor_milik_sendiri_tanpa_aksi_pengelola(self):
        asisten_user = Pengguna.objects.create(
            nama_pengguna=self.asleb.nama,
            nim_nik=self.asleb.nim,
            email='asisten-honor@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567899',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
        )
        asleb_lain = Asleb.objects.create(
            nama='Asisten Lab Lain',
            nim='2301999',
            no_hp='081200009999',
            email='asisten-lain@std.trisakti.ac.id',
            program_studi='Informatika',
            semester=5,
            tanggal_bergabung=date(2026, 6, 22),
        )
        honor_sendiri = HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 7, 1),
            total_pertemuan=3,
            status='diproses',
        )
        honor_lain = HonorAsleb.objects.create(
            asleb=asleb_lain,
            bulan=date(2026, 7, 1),
            total_pertemuan=4,
            status='diproses',
        )
        session = self.client.session
        session['pengguna_id'] = asisten_user.pk
        session.save()

        response = self.client.get(reverse('asleb:honor_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.asleb.nama)
        self.assertNotContains(response, asleb_lain.nama)
        self.assertContains(response, 'Honor sebelum potongan')
        self.assertContains(response, 'Biaya admin')
        self.assertContains(response, 'Total setelah potongan')
        self.assertNotContains(response, reverse('asleb:honor_update', args=[honor_sendiri.pk]))
        self.assertNotContains(response, reverse('asleb:honor_confirm_transfer', args=[honor_sendiri.pk]))
        self.assertNotContains(response, reverse('asleb:honor_update', args=[honor_lain.pk]))

    def test_asisten_lab_tidak_bisa_mengakses_edit_honor_melalui_url(self):
        asisten_user = Pengguna.objects.create(
            nama_pengguna=self.asleb.nama,
            nim_nik=self.asleb.nim,
            email='asisten-honor-url@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567898',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
        )
        honor = HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 7, 1),
            total_pertemuan=3,
        )
        session = self.client.session
        session['pengguna_id'] = asisten_user.pk
        session.save()

        response = self.client.get(reverse('asleb:honor_update', args=[honor.pk]))

        self.assertRedirects(response, reverse('dashboard:home'))

    def test_laboran_tidak_bisa_mengubah_atau_menghapus_honor_laboran_lain(self):
        laboran_lain = Pengguna.objects.create(
            nama_pengguna='Laboran Lain',
            nim_nik='LAB-LAIN-01',
            email='laboran-lain@example.com',
            password='rahasia123',
            no_hp='081200000001',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='laboran',
        )
        honor = HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 7, 1),
            total_pertemuan=3,
            status='diproses',
            assigned_laboran=laboran_lain,
        )

        edit_response = self.client.get(reverse('asleb:honor_update', args=[honor.pk]))
        delete_response = self.client.post(reverse('asleb:honor_delete', args=[honor.pk]))

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(HonorAsleb.objects.filter(pk=honor.pk).exists())

    def test_honor_yang_sudah_dibayar_tidak_bisa_diubah_atau_dihapus(self):
        honor = HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 7, 1),
            total_pertemuan=3,
            status='dibayar',
            assigned_laboran=self.pengguna,
            tanggal_transfer=date(2026, 7, 31),
            pic_transfer=self.pengguna.nama_pengguna,
            bukti_transfer=SimpleUploadedFile(
                'bukti-terkunci.pdf',
                b'%PDF-1.4\n%%EOF',
                content_type='application/pdf',
            ),
        )

        edit_response = self.client.get(reverse('asleb:honor_update', args=[honor.pk]))
        delete_response = self.client.post(reverse('asleb:honor_delete', args=[honor.pk]))

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(HonorAsleb.objects.filter(pk=honor.pk, status='dibayar').exists())

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

    def test_biaya_admin_dapat_diubah_dan_menghitung_ulang_honor_belum_dibayar(self):
        honor = HonorAsleb.objects.create(
            asleb=self.asleb, bulan=date(2026, 6, 1), total_pertemuan=3,
            metode_transfer='bank_lain', nomor_transfer='BCA 123456789', status='diproses',
        )
        response = self.client.post(reverse('asleb:honor_transfer_fees'), {
            'biaya_bni': 0,
            'biaya_bank_lain': 3000,
            'biaya_dana': 0,
            'biaya_shopeepay': 2000,
            'biaya_gopay': 2000,
            'biaya_ovo': 2000,
        })

        self.assertRedirects(response, reverse('asleb:honor_list'))
        honor.refresh_from_db()
        self.assertEqual(honor.biaya_admin, 3000)
        self.assertEqual(honor.jumlah, 144000)

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
        self.assertContains(response, '123456789')
        active_links = [link['title'] for link in response.context['sidebar_links'] if link['active']]
        self.assertEqual(active_links, ['Asisten Laboratorium'])
        asleb_group = next(link for link in response.context['sidebar_links'] if link['title'] == 'Asisten Laboratorium')
        self.assertEqual([child['title'] for child in asleb_group['children'] if child['active']], ['Rekap Honorarium'])

    def test_konfirmasi_transfer_honor_menyimpan_bukti_dan_status_dibayar(self):
        asisten_user = Pengguna.objects.create(
            nama_pengguna=self.asleb.nama,
            nim_nik=self.asleb.nim,
            email='siti.aslab@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567890',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
            is_verified=True,
        )
        honor = HonorAsleb.objects.create(
            asleb=self.asleb,
            bulan=date(2026, 4, 1),
            jumlah_praktikum=1,
            total_pertemuan=3,
            status='diproses',
            assigned_laboran=self.pengguna,
        )
        bukti = SimpleUploadedFile(
            'bukti-tf.pdf',
            b'%PDF-1.4\n% bukti transfer\n%%EOF',
            content_type='application/pdf',
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('asleb:honor_confirm_transfer', args=[honor.pk]), {
                'tanggal_transfer': '2026-04-30',
                'pic_transfer': 'Lab Admin',
                'bukti_transfer': bukti,
            })

        self.assertRedirects(response, reverse('asleb:honor_list'))
        honor.refresh_from_db()
        self.assertEqual(honor.status, 'dibayar')
        self.assertEqual(honor.pic_transfer, self.pengguna.nama_pengguna)
        self.assertTrue(honor.bukti_transfer)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [asisten_user.email])
        self.assertIn('Sudah Ditransfer', mail.outbox[0].subject)
        self.assertIn('Rp 147.000', mail.outbox[0].body)
        self.assertIn('30 April 2026', mail.outbox[0].body)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('asleb:honor_confirm_transfer', args=[honor.pk]), {
                'tanggal_transfer': '2026-04-30',
                'bukti_transfer': SimpleUploadedFile('ulang.jpg', b'ulang', content_type='image/jpeg'),
            })
        self.assertEqual(len(mail.outbox), 1)

    @patch('apps.asleb.views.generate_surat_honor_pdf', return_value=b'%PDF-1.4\n%%EOF')
    def test_honor_ditahan_visible_tetapi_tidak_dapat_dibayar_atau_masuk_surat(self, _pdf):
        assignment = self.create_active_assignment()
        from apps.pendaftaran_asleb.replacement_services import end_assignment_for_replacement
        end_assignment_for_replacement(
            assignment_id=assignment.pk, actor=self.pengguna, reason_type='resignation',
            reason='Mengundurkan diri', effective_date=date(2026, 10, 5),
        )

        held = HonorAsleb.objects.create(
            asleb=self.asleb, bulan=date(2026, 10, 1), total_pertemuan=3,
            status='diproses', assigned_laboran=self.pengguna,
        )
        other = Asleb.objects.create(
            nama='Aslab Tidak Ditahan', nim='HON-FREE', no_hp='0812',
            program_studi='Informatika', semester=5, tanggal_bergabung=date(2026, 7, 1),
        )
        eligible = HonorAsleb.objects.create(
            asleb=other, bulan=date(2026, 10, 1), total_pertemuan=2,
            status='diproses', assigned_laboran=self.pengguna,
        )
        self.assertFalse(HonorReassignment.objects.filter(honor=held).exists())

        response = self.client.get(reverse('asleb:honor_list'), {'bulan': '2026-10'})
        self.assertContains(response, self.asleb.nama)
        self.assertContains(response, 'Ditahan - proses penggantian')
        self.assertNotContains(response, reverse('asleb:honor_confirm_transfer', args=[held.pk]))

        HonorAsleb.objects.filter(pk=held.pk).update(assigned_laboran=None)
        self.client.post(reverse('asleb:honor_auto_assign_transfers'), {'bulan': '2026-10'})
        held.refresh_from_db()
        self.assertIsNone(held.assigned_laboran)
        HonorAsleb.objects.filter(pk=held.pk).update(assigned_laboran=self.pengguna)

        self.client.post(reverse('asleb:honor_confirm_transfer', args=[held.pk]), {
            'tanggal_transfer': '2026-10-31', 'pic_transfer': 'Lab Laboran',
            'bukti_transfer': SimpleUploadedFile('bukti.jpg', b'bukti', content_type='image/jpeg'),
        })
        held.refresh_from_db()
        self.assertEqual(held.status, 'diproses')

        response = self.client.post(reverse('asleb:surat_honor_generate'), {
            'bulan': '2026-10', 'nomor_surat': '001/HON/X/2026',
            'tanggal_surat': '2026-10-31', 'perihal': 'Honor Oktober',
        })
        self.assertRedirects(response, reverse('asleb:surat_honor_list'))
        surat = SuratHonorAsleb.objects.get()
        self.assertEqual(list(surat.honors.all()), [eligible])
        self.assertFalse(HonorReassignment.objects.filter(honor=held).exists())

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

    def test_absensi_modul_yang_sama_boleh_dipakai_pada_periode_baru(self):
        old_period = PeriodeAsleb.objects.create(
            tahun=2025,
            semester=2,
            mulai=date(2025, 7, 1),
            selesai=date(2025, 12, 31),
            pendaftaran_mulai=date(2025, 7, 1),
            pendaftaran_selesai=date(2025, 7, 30),
        )
        current_period = PeriodeAsleb.objects.create(
            tahun=2026,
            semester=2,
            mulai=date(2026, 7, 1),
            selesai=date(2026, 12, 31),
            pendaftaran_mulai=date(2026, 7, 1),
            pendaftaran_selesai=date(2026, 7, 30),
        )
        self.asleb.periode_aktif = current_period
        self.asleb.matkul = str(self.matkul)
        self.asleb.save(update_fields=['periode_aktif', 'matkul', 'diperbarui_pada'])
        modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=1,
            judul='Pengenalan Struktur Data',
            file=SimpleUploadedFile('modul-periode.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        jadwal = self.create_active_schedule()
        AbsensiAsleb.objects.create(
            asleb=self.asleb,
            periode=old_period,
            jadwal=jadwal,
            modul_praktikum=modul,
            tanggal_praktikum=date(2025, 8, 1),
            modul=1,
            materi_praktikum=modul.judul,
            file_modul=modul.file,
            bukti_foto=self.make_camera_photo('foto-periode-lama.png'),
            bukti_video=SimpleUploadedFile('video-periode-lama.mp4', b'video', content_type='video/mp4'),
        )

        form = AbsensiAslebForm(
            data={
                'modul_praktikum': modul.pk,
                'pekerjaan': 'Membantu praktikum periode baru',
                'latitude': '-6.1680678',
                'longitude': '106.7916257',
                'gps_accuracy': '10',
            },
            files={
                'bukti_foto': self.make_camera_photo('foto-periode-baru.png'),
                'bukti_video': SimpleUploadedFile('video-periode-baru.mp4', b'video', content_type='video/mp4'),
            },
            asleb=self.asleb,
            jadwal=jadwal,
        )

        self.assertTrue(form.is_valid(), form.errors)
        attendance = form.save(commit=False)
        attendance.asleb = self.asleb
        attendance.save()
        self.assertEqual(attendance.periode, current_period)

    def test_laporan_praktikum_menampilkan_kartu_kelas_mahasiswa(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Kelas Laporan',
            nim_nik='0640020777',
            email='kelas-laporan@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567877',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        PesertaPraktikum.objects.create(
            matkul=self.matkul,
            pengguna=mahasiswa,
            nim=mahasiswa.nim_nik,
            nama=mahasiswa.nama_pengguna,
        )
        TugasLaporanPraktikum.objects.create(
            judul='Laporan Struktur Data',
            matkul=self.matkul,
            batas_pengumpulan=timezone.now() + timedelta(days=2),
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('asleb:laporan_tugas_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kelas Praktikum')
        self.assertContains(response, self.matkul.nama)
        self.assertContains(response, reverse('asleb:laporan_kelas_detail', args=[self.matkul.pk]))
        self.assertNotContains(response, 'data-classroom-workspace')
        self.assertEqual(response.context['classroom_cards'][0]['task_count'], 1)

        detail_response = self.client.get(reverse('asleb:laporan_kelas_detail', args=[self.matkul.pk]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'Kelas aktif')
        self.assertContains(detail_response, 'Laporan Struktur Data')
        self.assertNotContains(detail_response, 'Kelas Praktikum')

    def test_laporan_praktikum_mahasiswa_tidak_bisa_membuka_kelas_lain(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Terbatas',
            nim_nik='0640020888',
            email='kelas-terbatas@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567888',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        PesertaPraktikum.objects.create(
            matkul=self.matkul,
            pengguna=mahasiswa,
            nim=mahasiswa.nim_nik,
            nama=mahasiswa.nama_pengguna,
        )
        matkul_lain = MataKuliahAsleb.objects.create(
            kode='KELAS-LAIN-01',
            nama='Mata Kuliah Tidak Diikuti',
            dosen='Dosen Lain',
            kelas='TIF-09',
        )
        TugasLaporanPraktikum.objects.create(
            judul='Laporan Kelas Lain',
            matkul=matkul_lain,
            batas_pengumpulan=timezone.now() + timedelta(days=2),
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('asleb:laporan_kelas_detail', args=[matkul_lain.pk]))

        self.assertEqual(response.status_code, 404)

    def test_laporan_praktikum_asisten_hanya_menampilkan_matkul_penugasan_aktif(self):
        pengguna_aslab = Pengguna.objects.create(
            nama_pengguna='Aslab Kelas Aktif',
            nim_nik=self.asleb.nim,
            email='aslab-kelas-aktif@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567899',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
        )
        self.create_active_assignment()
        TugasLaporanPraktikum.objects.create(
            judul='Laporan Matkul Diampu',
            matkul=self.matkul,
            batas_pengumpulan=timezone.now() + timedelta(days=2),
        )
        matkul_lain = MataKuliahAsleb.objects.create(
            kode='ASLAB-KELAS-LAIN',
            nama='Mata Kuliah Aslab Lain',
            dosen='Dosen Lain',
            kelas='TIF-08',
        )
        TugasLaporanPraktikum.objects.create(
            judul='Laporan Bukan Penugasan',
            matkul=matkul_lain,
            batas_pengumpulan=timezone.now() + timedelta(days=2),
        )
        session = self.client.session
        session['pengguna_id'] = pengguna_aslab.pk
        session.save()

        response = self.client.get(reverse('asleb:laporan_tugas_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.matkul.nama)
        self.assertNotContains(response, matkul_lain.nama)
        denied = self.client.get(reverse('asleb:laporan_kelas_detail', args=[matkul_lain.pk]))
        self.assertEqual(denied.status_code, 404)

    def test_format_tugas_laporan_menolak_tipe_file_aktif(self):
        form = TugasLaporanPraktikumForm(
            data={
                'judul': 'Laporan Modul 1',
                'matkul': self.matkul.pk,
                'pertemuan': 1,
                'deskripsi': 'Kumpulkan laporan.',
                'format_file': 'pdf,html',
                'ukuran_maksimal_mb': 10,
                'mulai_pengumpulan': '2026-07-01T08:00',
                'batas_pengumpulan': '2026-07-08T08:00',
                'aktif': True,
            },
            pengguna=self.pengguna,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('format_file', form.errors)

    def test_absensi_menolak_nomor_modul_yang_sudah_pernah_diabsen_meski_absensi_lama_tanpa_relasi_modul(self):
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
        modul_baru = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=2,
            judul='Array Dasar',
            file=SimpleUploadedFile('modul-baru-2.pdf', b'isi modul baru', content_type='application/pdf'),
        )
        jadwal = self.create_active_schedule()
        AbsensiAsleb.objects.create(
            asleb=self.asleb,
            jadwal=jadwal,
            modul_praktikum=None,
            tanggal_praktikum=timezone.localdate(),
            modul=2,
            materi_praktikum='Arsip Modul 2',
            pekerjaan='Membantu praktikum',
            file_modul=SimpleUploadedFile('arsip-modul-2.pdf', b'isi modul lama', content_type='application/pdf'),
            bukti_foto=self.make_camera_photo('foto-lama-2.png'),
            bukti_video=SimpleUploadedFile('video-lama-2.mp4', b'video lama', content_type='video/mp4'),
        )

        second_form = AbsensiAslebForm(
            data={
                'modul_praktikum': modul_baru.pk,
                'pekerjaan': 'Membantu praktikum revisi',
                'latitude': '-6.1680678',
                'longitude': '106.7916257',
                'gps_accuracy': '10',
            },
            files={
                'bukti_foto': self.make_camera_photo('foto-baru-2.png'),
                'bukti_video': SimpleUploadedFile('video-baru-2.mp4', b'video baru', content_type='video/mp4'),
            },
            asleb=self.asleb,
            jadwal=jadwal,
        )

        self.assertFalse(second_form.is_valid())
        self.assertIn('modul_praktikum', second_form.errors)
        self.assertIn('Modul 2 sudah pernah diabsen', str(second_form.errors['modul_praktikum']))

    def test_absensi_mengizinkan_nomor_modul_sama_pada_matkul_berbeda(self):
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
        modul_lama = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=1,
            judul='Modul Lama',
            file=SimpleUploadedFile('modul-lama.pdf', b'isi modul lama', content_type='application/pdf'),
        )
        jadwal_lama = self.create_active_schedule()
        AbsensiAsleb.objects.create(
            asleb=self.asleb,
            jadwal=jadwal_lama,
            modul_praktikum=modul_lama,
            tanggal_praktikum=timezone.localdate(),
            modul=1,
            materi_praktikum='Modul Lama',
            pekerjaan='Membantu praktikum lama',
            file_modul=SimpleUploadedFile('modul-lama-arsip.pdf', b'isi modul lama', content_type='application/pdf'),
            bukti_foto=self.make_camera_photo('foto-lama-matkul.png'),
            bukti_video=SimpleUploadedFile('video-lama-matkul.mp4', b'video lama', content_type='video/mp4'),
        )
        matkul_baru = MataKuliahAsleb.objects.create(
            kode='WEB_TIF01_TEST',
            nama='Pemrograman Web',
            dosen='Dosen Web',
            kelas='TIF-01',
        )
        PendaftaranAsleb.objects.create(
            nama=self.asleb.nama,
            nim=self.asleb.nim,
            no_hp=self.asleb.no_hp,
            email=self.asleb.email,
            program_studi=self.asleb.program_studi,
            semester=self.asleb.semester,
            matkul=matkul_baru,
            status='digenerate',
        )
        modul_baru = ModulPraktikum.objects.create(
            matkul=matkul_baru,
            nomor=1,
            judul='Modul Baru',
            file=SimpleUploadedFile('modul-baru.pdf', b'isi modul baru', content_type='application/pdf'),
        )
        jadwal_baru = JadwalPraktikum.objects.create(
            mata_kuliah=str(matkul_baru),
            kelas=matkul_baru.kelas,
            ruangan=self.test_room,
            pengampu=matkul_baru.dosen,
            hari='senin',
            waktu_mulai='13:00',
            waktu_selesai='15:00',
            status=JadwalPraktikum.STATUS_DITERIMA,
        )

        form = AbsensiAslebForm(
            data={
                'modul_praktikum': modul_baru.pk,
                'pekerjaan': 'Membantu praktikum baru',
                'latitude': '-6.1680678',
                'longitude': '106.7916257',
                'gps_accuracy': '10',
            },
            files={
                'bukti_foto': self.make_camera_photo('foto-baru-matkul.png'),
                'bukti_video': SimpleUploadedFile('video-baru-matkul.mp4', b'video baru', content_type='video/mp4'),
            },
            asleb=self.asleb,
            jadwal=jadwal_baru,
        )

        self.assertTrue(form.is_valid(), form.errors)

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

    def test_absensi_mengizinkan_maksimal_dua_modul_di_hari_yang_sama(self):
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
        modul_ketiga = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=6,
            judul='Tree',
            file=SimpleUploadedFile('modul-6.pdf', b'isi modul 6', content_type='application/pdf'),
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
        second_form = AbsensiAslebForm(
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

        self.assertTrue(second_form.is_valid(), second_form.errors)
        second_absensi = second_form.save(commit=False)
        second_absensi.asleb = self.asleb
        second_absensi.save()

        third_form = AbsensiAslebForm(
            data={
                'modul_praktikum': modul_ketiga.pk,
                'pekerjaan': 'Membantu praktikum sesi ketiga',
                'latitude': '-6.1680678',
                'longitude': '106.7916257',
                'gps_accuracy': '10',
            },
            files={
                'bukti_foto': self.make_camera_photo('foto-ketiga.png'),
                'bukti_video': SimpleUploadedFile('video-ketiga.mp4', b'video ketiga', content_type='video/mp4'),
            },
            asleb=self.asleb,
            jadwal=jadwal_diubah,
        )

        self.assertFalse(third_form.is_valid())
        self.assertIn('maksimal 2 modul', str(third_form.non_field_errors()))

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

    def test_asisten_lab_dapat_menghapus_laporan_dan_nilai_sinkronnya(self):
        asisten_user = Pengguna.objects.create(
            nama_pengguna=self.asleb.nama,
            nim_nik=self.asleb.nim,
            email='asisten-hapus-laporan@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567891',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='perempuan',
            role='asisten_lab',
        )
        self.asleb.matkul = str(self.matkul)
        self.asleb.status = 'aktif'
        self.asleb.save(update_fields=['matkul', 'status'])
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Laporan',
            nim_nik='0640020999',
            email='mahasiswa-laporan@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567899',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        peserta = PesertaPraktikum.objects.create(
            matkul=self.matkul,
            pengguna=mahasiswa,
            nim=mahasiswa.nim_nik,
            nama=mahasiswa.nama_pengguna,
        )
        modul = ModulPraktikum.objects.create(
            matkul=self.matkul,
            nomor=1,
            judul='Pengenalan',
            file=SimpleUploadedFile('modul-1.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        tugas = TugasLaporanPraktikum.objects.create(
            judul='Laporan Modul 1',
            matkul=self.matkul,
            modul=modul,
            batas_pengumpulan=timezone.now() + timedelta(days=1),
            dibuat_oleh=asisten_user,
        )
        laporan = PengumpulanLaporanPraktikum.objects.create(
            tugas=tugas,
            peserta=peserta,
            file_laporan=SimpleUploadedFile('laporan-mahasiswa.pdf', b'%PDF-1.4', content_type='application/pdf'),
            nilai=Decimal('88.00'),
            diperiksa_oleh=asisten_user,
        )
        hasil = HasilPraktikumMahasiswa.objects.create(
            peserta=peserta,
            modul=modul,
            nilai_laporan=Decimal('88.00'),
            dicatat_oleh=asisten_user,
        )
        session = self.client.session
        session['pengguna_id'] = asisten_user.pk
        session.save()

        response = self.client.post(reverse('asleb:laporan_delete', args=[laporan.pk]))

        self.assertRedirects(response, reverse('asleb:laporan_kelas_detail', args=[self.matkul.pk]))
        self.assertFalse(PengumpulanLaporanPraktikum.objects.filter(pk=laporan.pk).exists())
        hasil.refresh_from_db()
        self.assertIsNone(hasil.nilai_laporan)
        self.assertIsNone(hasil.nilai)
        self.assertTrue(Notifikasi.objects.filter(pengguna=mahasiswa, source_key=f'laporan-deleted:{laporan.pk}').exists())

    def test_preview_laporan_pdf_mengirim_header_dan_isi_pdf_utuh(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Preview',
            nim_nik='0640020888',
            email='mahasiswa-preview@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='081234567888',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        peserta = PesertaPraktikum.objects.create(
            matkul=self.matkul,
            pengguna=mahasiswa,
            nim=mahasiswa.nim_nik,
            nama=mahasiswa.nama_pengguna,
        )
        tugas = TugasLaporanPraktikum.objects.create(
            judul='Laporan Preview',
            matkul=self.matkul,
            batas_pengumpulan=timezone.now() + timedelta(days=1),
        )
        pdf_content = b'%PDF-1.4\npreview laporan\n%%EOF'
        laporan = PengumpulanLaporanPraktikum.objects.create(
            tugas=tugas,
            peserta=peserta,
            file_laporan=SimpleUploadedFile(
                'laporan-preview.pdf',
                pdf_content,
                content_type='application/pdf',
            ),
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()

        response = self.client.get(reverse('asleb:laporan_preview_file', args=[laporan.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Content-Length'], str(len(pdf_content)))
        self.assertIn('inline', response['Content-Disposition'])
        self.assertEqual(response.content, pdf_content)

    def create_active_schedule(self):
        return JadwalPraktikum.objects.create(
            mata_kuliah=str(self.matkul),
            kelas=self.matkul.kelas,
            ruangan=self.test_room,
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
                rekening='123456789',
                status='digenerate',
            )
