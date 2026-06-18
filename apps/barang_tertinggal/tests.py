from django.test import TestCase
from django.urls import reverse


class BarangTertinggalViewTests(TestCase):
    def test_page_loads(self):
        response = self.client.get(reverse('barang_tertinggal:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Barang Mahasiswa Tertinggal')

