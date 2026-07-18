from django.test import SimpleTestCase
from django.test.utils import override_script_prefix
from django.urls import reverse


class HealthCheckTests(SimpleTestCase):
    def test_health_check_does_not_require_login(self):
        response = self.client.get(reverse('health'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    @override_script_prefix('/labhub/')
    def test_prefixed_health_check_does_not_require_login(self):
        response = self.client.get('/health/')

        self.assertEqual(reverse('health'), '/labhub/health/')
        self.assertEqual(response.status_code, 200)
