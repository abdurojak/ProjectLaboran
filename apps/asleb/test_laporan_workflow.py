import io
import tempfile
import zipfile
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.pendaftaran_asleb.models import MataKuliahAsleb
from apps.pengguna.models import Pengguna
from apps.ruangan.models import RuanganLab

from .models import (
    Asleb, HasilPraktikumMahasiswa, ModulPraktikum,
    PengumpulanLaporanPraktikum, PesertaPraktikum,
    ProgresTugasPraktikum, TugasLaporanPraktikum,
)


class LaporanWorkflowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_dir = tempfile.TemporaryDirectory()
        cls.media_settings = override_settings(MEDIA_ROOT=cls.media_dir.name)
        cls.media_settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_settings.disable()
        cls.media_dir.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.lab = RuanganLab.objects.create(nama='Lab Workflow', kode='LAB-WORKFLOW')
        self.other_lab = RuanganLab.objects.create(nama='Lab Lain', kode='LAB-LAIN')
        self.course = MataKuliahAsleb.objects.create(
            kode='WORKFLOW-01', nama='Praktikum Workflow', dosen='Dosen Uji',
            kelas='TIF-01', laboratorium=self.lab,
        )
        self.other_course = MataKuliahAsleb.objects.create(
            kode='WORKFLOW-02', nama='Praktikum Lain', dosen='Dosen Uji',
            kelas='TIF-02', laboratorium=self.other_lab,
        )
        self.asleb = self.make_user('Asleb Uji', '06410001', 'asisten_lab')
        Asleb.objects.create(
            nama=self.asleb.nama_pengguna, nim=self.asleb.nim_nik,
            no_hp=self.asleb.no_hp, program_studi='Informatika',
            matkul=str(self.course), semester=4, tanggal_bergabung=timezone.localdate(),
        )
        self.laboran = self.make_user('Laboran Uji', 'LAB10001', 'laboran')
        self.other_laboran = self.make_user('Laboran Lain', 'LAB10002', 'laboran')
        self.lab.laboran_akun.add(self.laboran)
        self.other_lab.laboran_akun.add(self.other_laboran)
        self.student = self.make_user('Mahasiswa Uji', '06420001', 'mahasiswa')
        self.other_student = self.make_user('Mahasiswa Kedua', '06420002', 'mahasiswa')
        self.participant = PesertaPraktikum.objects.create(
            matkul=self.course, pengguna=self.student,
            nim=self.student.nim_nik, nama=self.student.nama_pengguna,
        )
        self.other_participant = PesertaPraktikum.objects.create(
            matkul=self.course, pengguna=self.other_student,
            nim=self.other_student.nim_nik, nama=self.other_student.nama_pengguna,
        )
        self.module = ModulPraktikum.objects.create(
            matkul=self.course, nomor=1, judul='Modul Uji',
            file=self.pdf('modul.pdf'),
        )

    def make_user(self, name, number, role):
        return Pengguna.objects.create(
            nama_pengguna=name, nim_nik=number,
            email=f'{number.lower()}@example.com', password='rahasia123',
            no_hp='081234567890', alamat='Jakarta', fakultas='Teknologi Industri',
            prodi='Informatika', gender='laki_laki', role=role, is_verified=True,
        )

    def login(self, user):
        session = self.client.session
        session['pengguna_id'] = user.pk
        session.save()

    def pdf(self, name='laporan.pdf'):
        return SimpleUploadedFile(name, b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF', content_type='application/pdf')

    def task(self, **kwargs):
        fields = {
            'judul': 'Laporan Workflow', 'matkul': self.course,
            'modul': self.module, 'dibuat_oleh': self.asleb,
            'batas_pengumpulan': timezone.now() + timedelta(days=2),
        }
        fields.update(kwargs)
        return TugasLaporanPraktikum.objects.create(**fields)

    def submit(self, task, *, name='laporan.pdf'):
        return self.client.post(
            reverse('asleb:laporan_submit', args=[task.pk]),
            {'file_laporan': self.pdf(name)},
        )

    def test_alur_asleb_mahasiswa_laboran_dan_status_per_peserta(self):
        self.login(self.asleb)
        start = timezone.localtime(timezone.now() - timedelta(minutes=5))
        end = timezone.localtime(timezone.now() + timedelta(days=2))
        response = self.client.post(reverse('asleb:laporan_tugas_create'), {
            'judul': 'Tugas Alur Lengkap', 'matkul': self.course.pk,
            'modul': self.module.pk, 'pertemuan': 1, 'deskripsi': 'Kumpulkan PDF',
            'format_file': 'pdf,zip', 'ukuran_maksimal_mb': 10,
            'mulai_pengumpulan': start.strftime('%Y-%m-%dT%H:%M'),
            'batas_pengumpulan': end.strftime('%Y-%m-%dT%H:%M'),
            'aktif': 'on', 'lampiran_instruksi': self.pdf('instruksi.pdf'),
        })
        self.assertEqual(response.status_code, 302, response.content[:500])
        task = TugasLaporanPraktikum.objects.get(judul='Tugas Alur Lengkap')
        self.assertEqual(task.dibuat_oleh, self.asleb)
        self.assertEqual(self.client.get(reverse('asleb:laporan_tugas_detail', args=[task.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('asleb:laporan_tugas_attachment', args=[task.pk])).status_code, 200)

        self.login(self.student)
        detail = self.client.get(reverse('asleb:laporan_tugas_detail', args=[task.pk]))
        self.assertContains(detail, 'Tugas Alur Lengkap')
        self.assertNotContains(detail, self.other_student.nama_pengguna)
        progress_url = reverse('asleb:laporan_tugas_progress', args=[task.pk])
        self.assertEqual(self.client.post(progress_url, {'status': 'in_progress'}).status_code, 302)
        self.assertEqual(ProgresTugasPraktikum.objects.get(tugas=task, peserta=self.participant).status, 'in_progress')
        self.assertEqual(self.submit(task).status_code, 302)
        report = PengumpulanLaporanPraktikum.objects.get(tugas=task, peserta=self.participant)
        self.assertEqual(ProgresTugasPraktikum.objects.get(tugas=task, peserta=self.participant).status, 'submitted')
        self.assertFalse(ProgresTugasPraktikum.objects.filter(tugas=task, peserta=self.other_participant).exists())
        self.assertEqual(self.submit(task).status_code, 200)
        self.assertEqual(PengumpulanLaporanPraktikum.objects.filter(tugas=task, peserta=self.participant).count(), 1)
        self.assertEqual(self.client.post(progress_url, {'status': 'graded'}).status_code, 403)

        self.login(self.laboran)
        self.assertEqual(self.client.get(reverse('asleb:laporan_tugas_list')).status_code, 200)
        self.assertEqual(self.client.post(reverse('asleb:laporan_start_review', args=[report.pk])).status_code, 302)
        self.assertEqual(ProgresTugasPraktikum.objects.get(tugas=task, peserta=self.participant).status, 'in_review')
        response = self.client.post(reverse('asleb:laporan_review', args=[report.pk]), {
            'nilai': '87.50', 'catatan_asisten': 'Baik',
        })
        self.assertEqual(response.status_code, 302, response.content[:500])
        report.refresh_from_db()
        self.assertEqual(report.nilai, Decimal('87.50'))
        self.assertEqual(report.diperiksa_oleh, self.laboran)
        self.assertEqual(ProgresTugasPraktikum.objects.get(tugas=task, peserta=self.participant).status, 'graded')
        self.assertFalse(ProgresTugasPraktikum.objects.filter(tugas=task, peserta=self.other_participant).exists())
        self.login(self.student)
        self.assertContains(self.client.get(reverse('asleb:laporan_tugas_detail', args=[task.pk])), '87.50')

    def test_izin_lintas_lab_dan_mahasiswa_lain(self):
        task = self.task()
        self.login(self.student)
        self.assertEqual(self.submit(task).status_code, 302)
        report = PengumpulanLaporanPraktikum.objects.get(tugas=task)
        self.login(self.other_laboran)
        self.assertEqual(self.client.get(reverse('asleb:laporan_review', args=[report.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('asleb:laporan_review', args=[report.pk]), {'nilai': '100'}).status_code, 403)
        self.assertEqual(self.client.get(reverse('asleb:laporan_download', args=[report.pk])).status_code, 403)
        self.login(self.other_student)
        self.assertEqual(self.client.get(reverse('asleb:laporan_download', args=[report.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('asleb:laporan_tugas_detail', args=[task.pk])).status_code, 200)
        self.assertNotContains(self.client.get(reverse('asleb:laporan_tugas_detail', args=[task.pk])), 'laporan.pdf')

    def test_asleb_menilai_dan_laboran_dapat_mengubah_nilai(self):
        task = self.task()
        self.login(self.student)
        self.assertEqual(self.submit(task).status_code, 302)
        report = PengumpulanLaporanPraktikum.objects.get(tugas=task)
        self.login(self.asleb)
        self.assertEqual(self.client.get(reverse('asleb:laporan_review', args=[report.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse('asleb:laporan_review', args=[report.pk]), {'nilai': '90'}).status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.nilai, Decimal('90'))
        self.assertEqual(report.diperiksa_oleh, self.asleb)
        self.login(self.laboran)
        self.assertEqual(self.client.post(reverse('asleb:laporan_review', args=[report.pk]), {'nilai': '85', 'catatan_asisten': 'Koreksi laboran'}).status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.nilai, Decimal('85'))
        self.assertEqual(report.diperiksa_oleh, self.laboran)
        self.assertNotEqual(self.client.get(reverse('asleb:laporan_tugas_create')).status_code, 200)
        self.assertEqual(self.client.get(reverse('asleb:laporan_tugas_update', args=[task.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('asleb:laporan_tugas_delete', args=[task.pk])).status_code, 403)

    def test_tenggat_dan_format_file(self):
        task = self.task()
        self.login(self.student)
        self.assertEqual(self.submit(task, name='palsu.pdf').status_code, 302)
        other = self.task(judul='Tugas Lain')
        self.assertEqual(self.client.post(
            reverse('asleb:laporan_submit', args=[other.pk]),
            {'file_laporan': SimpleUploadedFile('palsu.pdf', b'not pdf')},
        ).status_code, 200)
        self.assertFalse(PengumpulanLaporanPraktikum.objects.filter(tugas=other).exists())
        other.batas_pengumpulan = timezone.now() - timedelta(minutes=1)
        other.save(update_fields=['batas_pengumpulan'])
        self.assertEqual(self.submit(other).status_code, 302)
        self.assertFalse(PengumpulanLaporanPraktikum.objects.filter(tugas=other).exists())
        other.izinkan_terlambat = True
        other.save(update_fields=['izinkan_terlambat'])
        self.assertEqual(self.submit(other).status_code, 302)
        self.assertEqual(PengumpulanLaporanPraktikum.objects.get(tugas=other).status, 'terlambat')

    def test_modul_tidak_boleh_berubah_setelah_ada_pengumpulan(self):
        task = self.task()
        second_module = ModulPraktikum.objects.create(
            matkul=self.course, nomor=2, judul='Modul Kedua', file=self.pdf('modul2.pdf'),
        )
        self.login(self.student)
        self.assertEqual(self.submit(task).status_code, 302)
        self.login(self.asleb)
        start = timezone.localtime(task.mulai_pengumpulan)
        end = timezone.localtime(task.batas_pengumpulan)
        response = self.client.post(reverse('asleb:laporan_tugas_update', args=[task.pk]), {
            'judul': task.judul, 'matkul': self.course.pk, 'modul': second_module.pk,
            'deskripsi': 'Diubah', 'format_file': 'pdf', 'ukuran_maksimal_mb': 10,
            'mulai_pengumpulan': start.strftime('%Y-%m-%dT%H:%M'),
            'batas_pengumpulan': end.strftime('%Y-%m-%dT%H:%M'), 'aktif': 'on',
        })
        task.refresh_from_db()
        self.assertEqual(task.modul_id, self.module.pk, response.content[:500])

    def test_asleb_hanya_membuat_tugas_di_kelas_penugasan(self):
        self.login(self.asleb)
        start = timezone.localtime(timezone.now() - timedelta(minutes=5))
        end = timezone.localtime(timezone.now() + timedelta(days=2))
        response = self.client.post(reverse('asleb:laporan_tugas_create'), {
            'judul': 'Tugas Kelas Lain', 'matkul': self.other_course.pk,
            'deskripsi': 'Tidak boleh dibuat', 'format_file': 'pdf',
            'ukuran_maksimal_mb': 10,
            'mulai_pengumpulan': start.strftime('%Y-%m-%dT%H:%M'),
            'batas_pengumpulan': end.strftime('%Y-%m-%dT%H:%M'), 'aktif': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TugasLaporanPraktikum.objects.filter(judul='Tugas Kelas Lain').exists())

    def test_nilai_terhubung_ke_rekap_tapi_asleb_tidak_bisa_mengubahnya(self):
        task = self.task()
        hasil = HasilPraktikumMahasiswa.objects.create(
            peserta=self.participant, modul=self.module,
            status_absensi='hadir', nilai_realtime=Decimal('80'),
        )
        self.login(self.student)
        self.assertEqual(self.submit(task).status_code, 302)
        report = PengumpulanLaporanPraktikum.objects.get(tugas=task)
        self.login(self.laboran)
        review_url = reverse('asleb:laporan_review', args=[report.pk])
        for invalid in ('101', '-1', ''):
            self.assertEqual(self.client.post(review_url, {'nilai': invalid}).status_code, 200)
            report.refresh_from_db()
            self.assertIsNone(report.nilai)
        self.assertEqual(self.client.post(review_url, {'nilai': '90'}).status_code, 302)
        hasil.refresh_from_db()
        self.assertEqual(hasil.nilai_laporan, Decimal('90'))
        self.assertEqual(hasil.nilai, Decimal('85'))
        self.login(self.asleb)
        attendance_url = reverse('asleb:praktikum_nilai', args=[self.course.pk, self.module.pk])
        response = self.client.post(attendance_url, {
            'tanggal_praktikum': timezone.localdate().isoformat(),
            f'peserta-{self.participant.pk}-status_absensi': 'izin',
            f'peserta-{self.participant.pk}-nilai_realtime': '100',
            f'peserta-{self.participant.pk}-nilai_laporan': '100',
            f'peserta-{self.participant.pk}-catatan': 'Izin',
            f'peserta-{self.other_participant.pk}-status_absensi': 'hadir',
            f'peserta-{self.other_participant.pk}-catatan': '',
        })
        self.assertEqual(response.status_code, 302, response.content[:500])
        hasil.refresh_from_db()
        self.assertEqual(hasil.status_absensi, 'izin')
        self.assertEqual(hasil.nilai_realtime, Decimal('80'))
        self.assertEqual(hasil.nilai_laporan, Decimal('90'))
        self.login(self.laboran)
        self.assertEqual(self.client.post(attendance_url, {
            'tanggal_praktikum': timezone.localdate().isoformat(),
        }).status_code, 403)

    def test_zip_valid_diterima_dan_arsip_berbahaya_ditolak(self):
        task = self.task(format_file='pdf,zip')
        self.login(self.student)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('laporan.txt', 'hasil praktikum')
        response = self.client.post(reverse('asleb:laporan_submit', args=[task.pk]), {
            'file_laporan': SimpleUploadedFile('laporan.zip', buffer.getvalue()),
        })
        self.assertEqual(response.status_code, 302, response.content[:500])
        self.assertEqual(PengumpulanLaporanPraktikum.objects.filter(tugas=task).count(), 1)
        unsafe = self.task(judul='Tugas ZIP Lain', format_file='zip')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('../keluar.txt', 'isi')
        response = self.client.post(reverse('asleb:laporan_submit', args=[unsafe.pk]), {
            'file_laporan': SimpleUploadedFile('berbahaya.zip', buffer.getvalue()),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PengumpulanLaporanPraktikum.objects.filter(tugas=unsafe).exists())

    def test_tugas_terkumpul_tidak_boleh_dihapus(self):
        task = self.task()
        self.login(self.student)
        self.assertEqual(self.submit(task).status_code, 302)
        self.login(self.asleb)
        response = self.client.post(reverse('asleb:laporan_tugas_delete', args=[task.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(TugasLaporanPraktikum.objects.filter(pk=task.pk).exists())
