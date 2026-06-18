from django.test import TestCase
from django.urls import reverse


class RuanganViewTests(TestCase):
    def test_ruangan_page_loads(self):
        response = self.client.get(reverse('ruangan:ruangan_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lab Rekayasa Perangkat Lunak')

