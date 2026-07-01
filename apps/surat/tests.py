from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.pengguna.models import Pengguna

from .models import SuratPengadaan


class SuratLaboranTests(TestCase):
    def setUp(self):
        self.laboran = Pengguna.objects.create(
            nama_pengguna='Laboran Surat', nim_nik='LAB-SURAT-01', email='laboran-surat@trisakti.ac.id',
            password='rahasia123', no_hp='081200000001', alamat='Jakarta', fakultas='Teknologi Industri',
            prodi='Informatika', gender='laki_laki', role='laboran',
        )
        session = self.client.session
        session['pengguna_id'] = self.laboran.pk
        session.save()

    def test_laboran_dapat_membuka_menu_surat(self):
        response = self.client.get(reverse('surat:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Surat Laboran')
        self.assertContains(response, 'Permohonan Pengadaan')

    def test_mahasiswa_tidak_dapat_membuka_menu_surat(self):
        self.laboran.role = 'mahasiswa'
        self.laboran.save(update_fields=['role'])
        response = self.client.get(reverse('surat:list'))
        self.assertRedirects(response, reverse('dashboard:home'))

    def test_pdf_surat_pengadaan_dapat_diunduh(self):
        surat = SuratPengadaan.objects.create(
            nomor='001/LO.14.01/FTI-Kalab SKI/II/2026', tanggal=date(2026, 2, 3),
            isi='Sehubungan dengan persiapan pelaksanaan praktikum, kami mengajukan pengadaan kebutuhan fasilitas laboratorium.',
            dibuat_oleh=self.laboran,
        )
        response = self.client.get(reverse('surat:download_pdf', args=[surat.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertGreater(len(response.content), 50000)
