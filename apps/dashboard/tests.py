from django.test import TestCase
from django.urls import reverse


class DashboardViewTests(TestCase):
    def test_dashboard_page_loads(self):
        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Project Laboran')
