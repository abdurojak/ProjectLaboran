from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.inventaris.models import Barang
from apps.peminjaman.models import PeminjamanAlat


class DashboardViewTests(TestCase):
    def setUp(self):
        self.barang = Barang.objects.create(nama='Mikroskop', jumlah=5)

    def test_dashboard_page_loads(self):
        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'LabHub')

    def test_dashboard_shows_pending_peminjaman(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'Peminjaman Alat Diajukan')
        self.assertContains(response, 'Budi')
        self.assertContains(response, 'Terima')
        self.assertContains(response, 'Tolak')

    def test_accept_pending_peminjaman_changes_status_to_dipinjam(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        response = self.client.post(reverse('dashboard:peminjaman_accept', args=[peminjaman.pk]))
        peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(peminjaman.status, 'dipinjam')

    def test_reject_pending_peminjaman_deletes_record(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        response = self.client.post(reverse('dashboard:peminjaman_reject', args=[peminjaman.pk]))

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertFalse(PeminjamanAlat.objects.filter(pk=peminjaman.pk).exists())

    def test_dashboard_shows_replacement_action_for_lost_or_broken_peminjaman(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='hilang',
        )

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'Peminjaman Perlu Diganti')
        self.assertContains(response, 'Hilang')
        self.assertContains(response, 'Digantikan')

    def test_mark_replaced_changes_lost_or_broken_status_to_digantikan(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='rusak',
        )

        response = self.client.post(reverse('dashboard:peminjaman_replaced', args=[peminjaman.pk]))
        peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(peminjaman.status, 'digantikan')
