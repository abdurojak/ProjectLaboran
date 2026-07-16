import base64
import json
import os
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from apps.core.licensing import (
    LicenseError,
    build_license_key,
    enforce_configured_license,
    validate_license_key,
)


def _b64encode(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _canonical_payload(claims):
    value = json.dumps(claims, separators=(',', ':'), sort_keys=True).encode('utf-8')
    return _b64encode(value)


def _sign_payload(private_key, payload_bytes):
    payload = _b64encode(payload_bytes)
    signature = _b64encode(private_key.sign(payload.encode('ascii')))
    return f'{payload}.{signature}'


def _sign_claims(private_key, claims):
    payload_bytes = json.dumps(
        claims,
        separators=(',', ':'),
        sort_keys=True,
    ).encode('utf-8')
    return _sign_payload(private_key, payload_bytes)


class LicensingTests(SimpleTestCase):
    def setUp(self):
        self.private_key = ed25519.Ed25519PrivateKey.generate()
        self.private_key_pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.public_key_pem = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def build_license(self, **overrides):
        values = {
            'customer': 'Lab FTI',
            'fingerprint': 'server-utama',
            'expires_on': date(2030, 1, 31),
            'private_key_pem': self.private_key_pem,
        }
        values.update(overrides)
        return build_license_key(**values)

    def validate_license(self, license_key, **overrides):
        values = {
            'fingerprint': 'server-utama',
            'public_key_pem': self.public_key_pem,
            'today': date(2026, 7, 16),
        }
        values.update(overrides)
        return validate_license_key(license_key, **values)

    def test_license_valid_for_matching_fingerprint_with_v2_claims(self):
        claims = self.validate_license(self.build_license())

        self.assertEqual(
            claims,
            {
                'customer': 'Lab FTI',
                'expires_on': '2030-01-31',
                'fingerprint': 'server-utama',
                'version': 2,
            },
        )

    def test_build_accepts_private_key_pem_as_text(self):
        license_key = self.build_license(
            private_key_pem=self.private_key_pem.decode('ascii'),
        )

        self.assertEqual(self.validate_license(license_key)['version'], 2)

    def test_license_rejected_for_wrong_public_key(self):
        other_public_key_pem = (
            ed25519.Ed25519PrivateKey.generate()
            .public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

        with self.assertRaisesMessage(LicenseError, 'signature'):
            self.validate_license(
                self.build_license(),
                public_key_pem=other_public_key_pem,
            )

    def test_license_accepts_public_key_pem_as_text(self):
        claims = self.validate_license(
            self.build_license(),
            public_key_pem=self.public_key_pem.decode('ascii'),
        )

        self.assertEqual(claims['version'], 2)

    def test_license_rejected_when_payload_is_modified(self):
        license_key = self.build_license()
        payload, signature = license_key.split('.')
        claims = json.loads(base64.urlsafe_b64decode(payload + '=='))
        claims['customer'] = 'Changed customer'
        modified_license_key = f'{_canonical_payload(claims)}.{signature}'

        with self.assertRaisesMessage(LicenseError, 'signature'):
            self.validate_license(modified_license_key)

    def test_license_rejected_for_unsupported_version(self):
        license_key = _sign_claims(
            self.private_key,
            {
                'customer': 'Lab FTI',
                'expires_on': '2030-01-31',
                'fingerprint': 'server-utama',
                'version': 1,
            },
        )

        with self.assertRaisesMessage(LicenseError, 'version'):
            self.validate_license(license_key)

    def test_license_rejected_when_signed_payload_json_is_not_canonical(self):
        payload_bytes = (
            b'{"version":2, "customer":"Lab FTI",'
            b'"expires_on":"2030-01-31","fingerprint":"server-utama"}'
        )
        license_key = _sign_payload(self.private_key, payload_bytes)

        with self.assertRaisesMessage(LicenseError, 'canonical'):
            self.validate_license(license_key)

    def test_license_rejected_for_noncanonical_iso_expiration_date(self):
        license_key = _sign_claims(
            self.private_key,
            {
                'customer': 'Lab FTI',
                'expires_on': '2030-W05-4',
                'fingerprint': 'server-utama',
                'version': 2,
            },
        )

        with self.assertRaisesMessage(LicenseError, 'expiration date'):
            self.validate_license(license_key)

    def test_license_rejected_when_payload_base64url_retains_padding(self):
        claims = {
            'customer': 'Lab FTI',
            'expires_on': '2030-01-31',
            'fingerprint': 'server-utama',
            'version': 2,
        }
        payload_bytes = json.dumps(
            claims,
            separators=(',', ':'),
            sort_keys=True,
        ).encode('utf-8')
        payload = base64.urlsafe_b64encode(payload_bytes).decode('ascii')
        self.assertTrue(payload.endswith('='))
        signature = _b64encode(self.private_key.sign(payload.encode('ascii')))

        with self.assertRaises(LicenseError):
            self.validate_license(f'{payload}.{signature}')

    def test_license_rejected_when_signature_base64url_retains_padding(self):
        payload, signature = self.build_license().split('.')
        padded_signature = signature + '=' * (-len(signature) % 4)
        self.assertNotEqual(padded_signature, signature)

        with self.assertRaises(LicenseError):
            self.validate_license(f'{payload}.{padded_signature}')

    def test_license_rejected_when_signature_uses_standard_base64_characters(self):
        for customer_number in range(100):
            payload, signature = self.build_license(
                customer=f'Lab FTI {customer_number}',
            ).split('.')
            if '-' in signature or '_' in signature:
                break
        else:
            self.fail('Could not produce a signature containing URL-safe characters.')

        standard_signature = signature.replace('-', '+').replace('_', '/')
        self.assertNotEqual(standard_signature, signature)

        with self.assertRaises(LicenseError):
            self.validate_license(f'{payload}.{standard_signature}')

    def test_license_rejected_for_different_fingerprint(self):
        with self.assertRaisesMessage(LicenseError, 'fingerprint'):
            self.validate_license(
                self.build_license(),
                fingerprint='server-copy',
            )

    def test_license_rejected_when_expired(self):
        with self.assertRaisesMessage(LicenseError, 'expired'):
            self.validate_license(
                self.build_license(expires_on=date(2026, 7, 15)),
            )

    def test_license_rejected_for_invalid_expiration_date(self):
        license_key = _sign_claims(
            self.private_key,
            {
                'customer': 'Lab FTI',
                'expires_on': 'not-a-date',
                'fingerprint': 'server-utama',
                'version': 2,
            },
        )

        with self.assertRaisesMessage(LicenseError, 'expiration date'):
            self.validate_license(license_key)

    def test_license_rejected_when_payload_is_not_an_object(self):
        license_key = _sign_claims(self.private_key, ['not', 'an', 'object'])

        with self.assertRaisesMessage(LicenseError, 'payload'):
            self.validate_license(license_key)

    def test_license_rejected_when_payload_json_is_malformed(self):
        payload = _b64encode(b'{not-json')
        signature = _b64encode(self.private_key.sign(payload.encode('ascii')))

        with self.assertRaisesMessage(LicenseError, 'payload'):
            self.validate_license(f'{payload}.{signature}')

    def test_license_rejected_when_payload_base64_is_malformed(self):
        payload = '***'
        signature = _b64encode(self.private_key.sign(payload.encode('ascii')))

        with self.assertRaisesMessage(LicenseError, 'payload'):
            self.validate_license(f'{payload}.{signature}')

    def test_license_rejected_for_malformed_base64(self):
        with self.assertRaises(LicenseError):
            self.validate_license('***.***')

    def test_build_rejects_malformed_private_key(self):
        with self.assertRaisesMessage(LicenseError, 'private key'):
            self.build_license(private_key_pem=b'not-a-private-key')

    def test_build_rejects_non_ed25519_private_key(self):
        rsa_private_key_pem = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        ).private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        with self.assertRaisesMessage(LicenseError, 'Ed25519 private key'):
            self.build_license(private_key_pem=rsa_private_key_pem)

    def test_validate_rejects_malformed_public_key(self):
        with self.assertRaisesMessage(LicenseError, 'public key'):
            self.validate_license(
                self.build_license(),
                public_key_pem=b'not-a-public-key',
            )

    def test_validate_rejects_non_ed25519_public_key(self):
        rsa_public_key_pem = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        ).public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        with self.assertRaisesMessage(LicenseError, 'Ed25519 public key'):
            self.validate_license(
                self.build_license(),
                public_key_pem=rsa_public_key_pem,
            )

    def test_enforce_configured_license_uses_embedded_public_key(self):
        environment = {
            'LABHUB_LICENSE_KEY': 'configured-license',
            'LABHUB_LICENSE_VERIFICATION_SECRET': 'must-not-be-used',
        }

        with (
            patch.dict(os.environ, environment, clear=True),
            patch('apps.core.license_public_key.PUBLIC_KEY_PEM', 'embedded-public-key'),
            patch('apps.core.licensing.get_server_fingerprint', return_value='server-id'),
            patch('apps.core.licensing.validate_license_key') as validate,
        ):
            enforce_configured_license()

        validate.assert_called_once_with(
            'configured-license',
            fingerprint='server-id',
            public_key_pem='embedded-public-key',
        )


class GenerateLicenseCommandTests(SimpleTestCase):
    def setUp(self):
        self.private_key = ed25519.Ed25519PrivateKey.generate()
        self.private_key_pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.public_key_pem = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def test_command_reads_text_private_key_file_and_outputs_valid_v2_license(self):
        output = StringIO()

        with TemporaryDirectory() as temp_dir:
            private_key_path = Path(temp_dir) / 'license-private.pem'
            private_key_path.write_text(
                self.private_key_pem.decode('ascii'),
                encoding='utf-8',
            )
            environment = {
                'LABHUB_LICENSE_PRIVATE_KEY_FILE': str(private_key_path),
                'LABHUB_LICENSE_SIGNING_SECRET': 'must-not-be-used',
            }

            with patch.dict(os.environ, environment, clear=True):
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

        claims = validate_license_key(
            output.getvalue().strip(),
            fingerprint='server-utama',
            public_key_pem=self.public_key_pem,
            today=date(2026, 7, 16),
        )
        self.assertEqual(claims['version'], 2)

    def test_command_requires_private_key_file_environment_variable(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesMessage(CommandError, 'LABHUB_LICENSE_PRIVATE_KEY_FILE'),
        ):
            call_command(
                'generate_labhub_license',
                '--customer',
                'Lab FTI',
                '--fingerprint',
                'server-utama',
                '--expires-on',
                '2030-01-31',
            )

    def test_command_normalizes_unreadable_private_key_file_error(self):
        with TemporaryDirectory() as temp_dir:
            private_key_path = Path(temp_dir) / 'missing-private-key.pem'
            environment = {'LABHUB_LICENSE_PRIVATE_KEY_FILE': str(private_key_path)}

            with (
                patch.dict(os.environ, environment, clear=True),
                self.assertRaisesMessage(CommandError, 'private key file'),
            ):
                call_command(
                    'generate_labhub_license',
                    '--customer',
                    'Lab FTI',
                    '--fingerprint',
                    'server-utama',
                    '--expires-on',
                    '2030-01-31',
                )

    def test_command_normalizes_invalid_expiration_date_error(self):
        with TemporaryDirectory() as temp_dir:
            private_key_path = Path(temp_dir) / 'license-private.pem'
            private_key_path.write_text(
                self.private_key_pem.decode('ascii'),
                encoding='utf-8',
            )
            environment = {'LABHUB_LICENSE_PRIVATE_KEY_FILE': str(private_key_path)}

            with (
                patch.dict(os.environ, environment, clear=True),
                self.assertRaisesMessage(CommandError, 'YYYY-MM-DD'),
            ):
                call_command(
                    'generate_labhub_license',
                    '--customer',
                    'Lab FTI',
                    '--fingerprint',
                    'server-utama',
                    '--expires-on',
                    'not-a-date',
                )


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
