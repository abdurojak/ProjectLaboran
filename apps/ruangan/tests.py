from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.pengguna.models import Pengguna
from apps.ruangan.models import FotoRuanganLab, GrupRuanganGabungan, RuanganLab


class RuanganViewTests(TestCase):
    def setUp(self):
        pengguna = Pengguna.objects.create(
            nama_pengguna='Lab Admin',
            nim_nik='ADM-RUANGAN',
            email='admin-ruangan@example.com',
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
        RuanganLab.objects.get_or_create(
            kode='LAB-RPL',
            defaults={'nama': 'Lab Rekayasa Perangkat Lunak', 'kapasitas': 20, 'warna': 'teal', 'aktif': True},
        )

    def test_ruangan_page_loads(self):
        response = self.client.get(reverse('ruangan:ruangan_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lab Rekayasa Perangkat Lunak')
        self.assertNotContains(response, 'Tambah Kegiatan')
        self.assertContains(response, reverse('ruangan:foto_create', args=[RuanganLab.objects.get(kode='LAB-RPL').pk]))

    def test_ruangan_page_mengambil_data_dari_database(self):
        RuanganLab.objects.all().delete()
        RuanganLab.objects.create(
            nama='Lab Testing Database',
            kode='LAB-TEST',
            deskripsi='Ruang lab dari database.',
            kapasitas=12,
            warna='blue',
        )

        response = self.client.get(reverse('ruangan:ruangan_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lab Testing Database')
        self.assertContains(response, 'LAB-TEST')
        self.assertContains(response, 'Kapasitas 12 mahasiswa')
        self.assertEqual(response.context['jumlah_ruangan'], 1)

    def test_ruangan_page_menampilkan_grup_ruangan_gabungan(self):
        lab_rpl = RuanganLab.objects.get(kode='LAB-RPL')
        lab_ski = RuanganLab.objects.create(
            nama='Lab Sistem Keamanan Informasi',
            kode='LAB-SKI-UI',
            deskripsi='Lab pasangan untuk pengujian.',
            kapasitas=18,
            warna='amber',
        )
        grup = GrupRuanganGabungan.objects.create(
            nama='Lab RPL dan Lab SKI',
            deskripsi='Dua lab berdampingan untuk kelas besar.',
        )
        grup.ruangan.set([lab_rpl, lab_ski])

        response = self.client.get(reverse('ruangan:ruangan_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Grup Ruangan Gabungan')
        self.assertContains(response, 'Lab RPL dan Lab SKI')
        self.assertContains(response, 'Kapasitas gabungan 38 mahasiswa')

    def test_laboran_dapat_upload_foto_lab(self):
        ruangan = RuanganLab.objects.get(kode='LAB-RPL')
        image = SimpleUploadedFile(
            'lab-rpl.jpg',
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b',
            content_type='image/gif',
        )

        response = self.client.post(reverse('ruangan:foto_create', args=[ruangan.pk]), {
            'gambar': image,
            'judul': 'Tampak depan Lab RPL',
            'urutan': 1,
        })

        self.assertRedirects(response, reverse('ruangan:ruangan_list'))
        foto = FotoRuanganLab.objects.get(ruangan=ruangan)
        self.assertEqual(foto.judul, 'Tampak depan Lab RPL')

        list_response = self.client.get(reverse('ruangan:ruangan_list'))
        self.assertContains(list_response, 'Galeri Foto')
        self.assertContains(list_response, foto.gambar.url)
        self.assertContains(list_response, reverse('ruangan:foto_update', args=[foto.pk]))
        self.assertContains(list_response, reverse('ruangan:foto_delete', args=[foto.pk]))

    def test_mahasiswa_tidak_dapat_mengelola_foto_lab(self):
        mahasiswa = Pengguna.objects.create(
            nama_pengguna='Mahasiswa Ruangan',
            nim_nik='2401001001',
            email='mahasiswa-ruangan@std.trisakti.ac.id',
            password='rahasia123',
            no_hp='',
            alamat='Jakarta',
            fakultas='Teknologi Industri',
            prodi='Informatika',
            gender='laki_laki',
            role='mahasiswa',
        )
        session = self.client.session
        session['pengguna_id'] = mahasiswa.pk
        session.save()
        ruangan = RuanganLab.objects.get(kode='LAB-RPL')

        response = self.client.get(reverse('ruangan:foto_create', args=[ruangan.pk]))

        self.assertRedirects(response, reverse('ruangan:ruangan_list'))

        list_response = self.client.get(reverse('ruangan:ruangan_list'))
        self.assertNotContains(list_response, reverse('ruangan:foto_create', args=[ruangan.pk]))

