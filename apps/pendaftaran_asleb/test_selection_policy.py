from datetime import date
import shutil
import tempfile

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.pengguna.models import Pengguna

from .models import KeputusanSeleksiAsleb, MataKuliahAsleb, PendaftaranAsleb, PeriodeAsleb
from .selection import academic_semester_from_nim, acceptance_limit


class SelectionPolicyTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_dir = tempfile.mkdtemp(prefix='aslab-selection-')
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.period = PeriodeAsleb.get_for_date(date(2026, 9, 1))
        self.laboran = Pengguna.objects.create(
            nama_pengguna='Laboran Seleksi', nim_nik='LAB-SELEKSI',
            email='seleksi@example.com', password='testing', no_hp='081234567890',
            alamat='Jakarta', fakultas='FTI', prodi='Informatika',
            gender='laki_laki', role='laboran',
        )
        session = self.client.session
        session['pengguna_id'] = self.laboran.pk
        session.save()
        self.courses = [
            MataKuliahAsleb.objects.create(
                kode=f'SELECTION-{number}', nama=f'Matkul Seleksi {number}',
                dosen='Dosen', kelas='TIF-01', maksimal_aslab=2,
            )
            for number in range(1, 5)
        ]

    def registration(self, nim, course, status='diajukan', transcript=None):
        item = PendaftaranAsleb.objects.create(
            nama='Calon Aslab', nim=nim, no_hp='081200000001',
            email=f'{nim}@std.trisakti.ac.id', program_studi='Informatika',
            semester=7, matkul=course, periode=self.period, status=status,
        )
        if transcript is not None:
            item.transkrip.save('nilai.txt', ContentFile(transcript.encode()), save=True)
        return item

    def test_semester_dihitung_dari_angkatan_dan_periode(self):
        self.assertEqual(academic_semester_from_nim('064102500007', self.period), 3)
        self.assertEqual(academic_semester_from_nim('065002300021', self.period), 7)
        self.assertEqual(acceptance_limit('064102400007', self.period), 2)
        self.assertEqual(acceptance_limit('064102500007', self.period), 1)
        first_half = PeriodeAsleb.get_for_date(date(2027, 3, 1))
        self.assertEqual(academic_semester_from_nim('064102500007', first_half), 4)
        self.assertEqual(acceptance_limit('064102500007', first_half), 1)

    def test_angkatan_2025_hanya_satu_tanpa_konfirmasi_tertulis(self):
        nim = '064102500007'
        self.registration(nim, self.courses[0], status='diterima')
        second = self.registration(nim, self.courses[1])
        url = reverse('pendaftaran_asleb:pendaftaran_accept', args=[second.pk])

        response = self.client.post(url)

        second.refresh_from_db()
        self.assertEqual(second.status, 'diajukan')
        self.assertEqual(response.status_code, 302)
        self.assertIn('konfirmasi', response.url)

        response = self.client.post(url, {'override_phrase': 'TERIMA DI LUAR BATAS'})
        second.refresh_from_db()
        self.assertEqual(second.status, 'diterima')
        self.assertTrue(KeputusanSeleksiAsleb.objects.filter(
            source_pendaftaran_id=second.pk, melewati_batas=True,
        ).exists())

    def test_angkatan_2024_boleh_dua_tapi_yang_ketiga_perlu_konfirmasi(self):
        nim = '064102400007'
        self.registration(nim, self.courses[0], status='diterima')
        second = self.registration(nim, self.courses[1])
        third = self.registration(nim, self.courses[2])

        self.client.post(reverse('pendaftaran_asleb:pendaftaran_accept', args=[second.pk]))
        second.refresh_from_db()
        self.assertEqual(second.status, 'diterima')

        response = self.client.post(reverse('pendaftaran_asleb:pendaftaran_accept', args=[third.pk]))
        third.refresh_from_db()
        self.assertEqual(third.status, 'diajukan')
        self.assertIn('konfirmasi', response.url)

    def test_matkul_yang_sudah_diterima_tidak_boleh_diterima_dua_kali(self):
        nim = '064102400007'
        self.registration(nim, self.courses[0], status='diterima')
        duplicate = self.registration(nim, self.courses[0])

        self.client.post(reverse('pendaftaran_asleb:pendaftaran_accept', args=[duplicate.pk]))

        duplicate.refresh_from_db()
        self.assertEqual(duplicate.status, 'diajukan')

    def test_edit_form_tidak_bisa_menerima_tanpa_validasi_kuota(self):
        item = self.registration('064102500007', self.courses[0])
        response = self.client.post(
            reverse('pendaftaran_asleb:pendaftaran_update', args=[item.pk]),
            {
                'nama': item.nama, 'nim': item.nim, 'no_hp': item.no_hp,
                'email': item.email, 'program_studi': item.program_studi,
                'semester': item.semester, 'matkul': item.matkul_id,
                'metode_rekening': 'bni', 'rekening': '1234567890',
                'nama_pemilik_rekening': item.nama, 'nilai_transkrip': 'A',
                'status': 'diterima',
            },
        )

        item.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(item.status, 'diajukan')

    def test_pemindahan_wajib_nilai_b_di_matkul_tujuan(self):
        nim = '064102400007'
        source, target = self.courses[:2]
        item = self.registration(
            nim, source, transcript=f'{nim}\n{source.nama} A\n{target.nama} C',
        )
        url = reverse('pendaftaran_asleb:pendaftaran_move', args=[item.pk])

        self.client.post(url, {'target_matkul': target.pk, 'verify_grade': 'on'})
        item.refresh_from_db()
        self.assertEqual(item.matkul, source)

        item.transkrip.save(
            'nilai-lengkap.txt',
            ContentFile(f'{nim}\n{source.nama} A\n{target.nama} B'.encode()),
            save=True,
        )
        self.client.post(url, {'target_matkul': target.pk, 'verify_grade': 'on'})
        item.refresh_from_db()
        self.assertEqual(item.matkul, target)
        self.assertEqual(item.status, 'diterima')
        decision = KeputusanSeleksiAsleb.objects.get(source_pendaftaran_id=item.pk)
        self.assertEqual(decision.matkul_pilihan, source)
        self.assertEqual(decision.matkul_tujuan, target)
        self.assertEqual(decision.nilai_tujuan, 'B')

        self.client.post(reverse('pendaftaran_asleb:pendaftaran_generate_all_accepted'))
        self.assertFalse(PendaftaranAsleb.objects.filter(pk=item.pk).exists())
        self.assertTrue(KeputusanSeleksiAsleb.objects.filter(pk=decision.pk).exists())

    def test_nilai_umum_tidak_boleh_dipakai_untuk_matkul_tujuan(self):
        nim = '064102400007'
        source, target = self.courses[:2]
        item = self.registration(nim, source, transcript=f'{nim}\n{source.nama} A')
        url = reverse('pendaftaran_asleb:pendaftaran_move', args=[item.pk])

        self.client.post(url, {'target_matkul': target.pk, 'verify_grade': 'on'})

        item.refresh_from_db()
        self.assertEqual(item.matkul, source)
