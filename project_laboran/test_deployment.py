import json
import os
import subprocess
import sys

from django.conf import settings
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

    @override_script_prefix('/labhub/')
    def test_prefixed_dashboard_redirects_to_prefixed_login(self):
        response = self.client.get('/', SCRIPT_NAME='/labhub')

        self.assertEqual(
            response.headers['Location'],
            '/labhub/pengguna/login/?next=/labhub/',
        )

    def test_production_url_settings_follow_script_prefix(self):
        environment = os.environ.copy()
        environment.update({
            'DEBUG': 'True',
            'FORCE_SCRIPT_NAME': '/labhub',
            'USE_SQLITE_FOR_TESTS': 'True',
        })
        environment.pop('MEDIA_URL', None)
        command = (
            'import json; '
            'from django.conf import settings; '
            'print(json.dumps({'
            '"static": settings.STATIC_URL, '
            '"media": settings.MEDIA_URL, '
            '"session_cookie": settings.SESSION_COOKIE_PATH, '
            '"csrf_cookie": settings.CSRF_COOKIE_PATH'
            '}))'
        )

        output = subprocess.check_output(
            [sys.executable, '-c', command],
            cwd=os.fspath(settings.BASE_DIR),
            env=environment,
            text=True,
        )

        self.assertEqual(json.loads(output), {
            'static': '/labhub/static/',
            'media': '/labhub/media/',
            'session_cookie': '/labhub/',
            'csrf_cookie': '/labhub/',
        })
