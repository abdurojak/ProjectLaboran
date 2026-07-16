from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.apps import apps
from django.test import SimpleTestCase, override_settings

from apps.core.licensing import (
    LicenseError,
    build_license_key,
    validate_license_key,
)


class LicensingTests(SimpleTestCase):
    def test_license_valid_for_matching_fingerprint(self):
        license_key = build_license_key(
            customer='Lab FTI',
            fingerprint='server-utama',
            expires_on=date(2030, 1, 31),
            signing_secret='rahasia-generator',
        )

        claims = validate_license_key(
            license_key,
            fingerprint='server-utama',
            verification_secret='rahasia-generator',
            today=date(2026, 7, 16),
        )

        self.assertEqual(claims['customer'], 'Lab FTI')
        self.assertEqual(claims['fingerprint'], 'server-utama')
        self.assertEqual(claims['expires_on'], '2030-01-31')

    def test_license_rejected_for_different_fingerprint(self):
        license_key = build_license_key(
            customer='Lab FTI',
            fingerprint='server-utama',
            expires_on=date(2030, 1, 31),
            signing_secret='rahasia-generator',
        )

        with self.assertRaisesMessage(LicenseError, 'fingerprint'):
            validate_license_key(
                license_key,
                fingerprint='server-copy',
                verification_secret='rahasia-generator',
                today=date(2026, 7, 16),
            )

    def test_license_rejected_when_expired(self):
        license_key = build_license_key(
            customer='Lab FTI',
            fingerprint='server-utama',
            expires_on=date(2026, 7, 15),
            signing_secret='rahasia-generator',
        )

        with self.assertRaisesMessage(LicenseError, 'expired'):
            validate_license_key(
                license_key,
                fingerprint='server-utama',
                verification_secret='rahasia-generator',
                today=date(2026, 7, 16),
            )

    def test_license_rejected_when_signature_is_wrong(self):
        license_key = build_license_key(
            customer='Lab FTI',
            fingerprint='server-utama',
            expires_on=date(2030, 1, 31),
            signing_secret='rahasia-generator',
        )

        with self.assertRaisesMessage(LicenseError, 'signature'):
            validate_license_key(
                license_key,
                fingerprint='server-utama',
                verification_secret='rahasia-lain',
                today=date(2026, 7, 16),
            )

    def test_generate_license_command_outputs_valid_license(self):
        output = StringIO()

        with patch.dict('os.environ', {'LABHUB_LICENSE_SIGNING_SECRET': 'rahasia-generator'}):
            call_command(
                'generate_labhub_license',
                '--customer',
                'Lab FTI',
                '--fingerprint',
                'server-utama',
                '--expires-on',
                '2030-01-31',
                stdout=output,
            )

        license_key = output.getvalue().strip()
        claims = validate_license_key(
            license_key,
            fingerprint='server-utama',
            verification_secret='rahasia-generator',
            today=date(2026, 7, 16),
        )

        self.assertEqual(claims['customer'], 'Lab FTI')


class LicenseStartupTests(SimpleTestCase):
    @override_settings(LABHUB_LICENSE_ENFORCED=False)
    def test_ready_does_not_validate_license_when_disabled(self):
        core_config = apps.get_app_config('core')

        with patch('apps.core.licensing.enforce_configured_license') as enforce:
            core_config.ready()

        enforce.assert_not_called()

    @override_settings(LABHUB_LICENSE_ENFORCED=True)
    def test_ready_validates_license_when_enabled(self):
        core_config = apps.get_app_config('core')

        with patch('apps.core.licensing.enforce_configured_license') as enforce:
            core_config.ready()

        enforce.assert_called_once_with()
