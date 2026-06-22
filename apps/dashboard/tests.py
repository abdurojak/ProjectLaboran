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

    def test_pending_peminjaman_actions_do_not_use_confirmation(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        response = self.client.get(reverse('dashboard:home'))
        content = response.content.decode()
        pending_section = content.split('Peminjaman Alat Diajukan', 1)[1].split('Barang Yang Dipinjam', 1)[0]

        self.assertNotIn('data-confirm-message', pending_section)

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

    def test_accept_pending_peminjaman_rejects_when_stock_is_no_longer_available(self):
        barang = Barang.objects.create(nama='Proyektor', jumlah=1)
        accepted = PeminjamanAlat.objects.create(
            barang=barang,
            nama_peminjam='Budi',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )
        waiting = PeminjamanAlat.objects.create(
            barang=barang,
            nama_peminjam='Siti',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='diajukan',
        )

        self.client.post(reverse('dashboard:peminjaman_accept', args=[accepted.pk]))
        response = self.client.post(reverse('dashboard:peminjaman_accept', args=[waiting.pk]), follow=True)
        waiting.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(waiting.status, 'diajukan')
        self.assertEqual(barang.stok_tersedia, 0)
        self.assertContains(response, 'Stok Proyektor tidak cukup. Tersedia 0 unit.')

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

    def test_dashboard_shows_borrowed_peminjaman_actions(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'Barang Yang Dipinjam')
        self.assertContains(response, 'Siti')
        self.assertContains(response, 'Dikembalikan')
        self.assertContains(response, 'Hilang')
        self.assertContains(response, 'Rusak')

    def test_borrowed_and_replacement_actions_use_confirmation(self):
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )
        PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Budi',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='rusak',
        )

        response = self.client.get(reverse('dashboard:home'))

        self.assertContains(response, 'data-confirm-message="', count=4)
        self.assertContains(response, 'data-confirmation-modal')
        self.assertNotContains(response, 'window.confirm')
        self.assertContains(response, 'Yakin tandai peminjaman ini sudah dikembalikan?')
        self.assertContains(response, 'Yakin tandai barang ini hilang?')
        self.assertContains(response, 'Yakin tandai barang ini rusak?')
        self.assertContains(response, 'Yakin tandai barang ini sudah digantikan?')

    def test_mark_borrowed_as_returned_changes_status_to_dikembalikan(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )

        response = self.client.post(reverse('dashboard:peminjaman_returned', args=[peminjaman.pk]))
        peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(peminjaman.status, 'dikembalikan')

    def test_mark_borrowed_as_lost_changes_status_to_hilang(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )

        response = self.client.post(reverse('dashboard:peminjaman_lost', args=[peminjaman.pk]))
        peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(peminjaman.status, 'hilang')

    def test_mark_borrowed_as_broken_changes_status_to_rusak(self):
        peminjaman = PeminjamanAlat.objects.create(
            barang=self.barang,
            nama_peminjam='Siti',
            jumlah=1,
            tanggal_pinjam=timezone.localdate(),
            tanggal_kembali=timezone.localdate(),
            status='dipinjam',
        )

        response = self.client.post(reverse('dashboard:peminjaman_broken', args=[peminjaman.pk]))
        peminjaman.refresh_from_db()

        self.assertRedirects(response, reverse('dashboard:home'))
        self.assertEqual(peminjaman.status, 'rusak')

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
