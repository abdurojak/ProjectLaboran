import base64
import hashlib
import hmac
import json
import os
from datetime import date
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


class LicenseError(ImproperlyConfigured):
    pass


def build_license_key(customer, fingerprint, expires_on, signing_secret):
    if not signing_secret:
        raise LicenseError('License signing secret is required.')

    claims = {
        'customer': customer,
        'expires_on': expires_on.isoformat(),
        'fingerprint': fingerprint,
    }
    payload = _b64encode(_json_dumps(claims))
    signature = _sign(payload, signing_secret)
    return f'{payload}.{signature}'


def validate_license_key(license_key, fingerprint, verification_secret, today=None):
    if not license_key:
        raise LicenseError('License key is required.')
    if not verification_secret:
        raise LicenseError('License verification secret is required.')

    payload, signature = _split_license_key(license_key)
    expected_signature = _sign(payload, verification_secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise LicenseError('License signature is invalid.')

    claims = _load_claims(payload)
    if claims.get('fingerprint') != fingerprint:
        raise LicenseError('License fingerprint does not match this server.')

    expires_on = date.fromisoformat(claims['expires_on'])
    if (today or date.today()) > expires_on:
        raise LicenseError('License has expired.')

    return claims


def get_server_fingerprint():
    override = os.getenv('LABHUB_LICENSE_FINGERPRINT', '').strip()
    if override:
        return override

    machine_id = _read_first_existing(
        Path('/etc/machine-id'),
        Path('/var/lib/dbus/machine-id'),
    )
    if machine_id:
        return machine_id

    return os.uname().nodename if hasattr(os, 'uname') else os.getenv('COMPUTERNAME', '')


def enforce_configured_license():
    validate_license_key(
        os.getenv('LABHUB_LICENSE_KEY', '').strip(),
        fingerprint=get_server_fingerprint(),
        verification_secret=os.getenv('LABHUB_LICENSE_VERIFICATION_SECRET', '').strip(),
    )


def _split_license_key(license_key):
    try:
        payload, signature = license_key.split('.', 1)
    except ValueError as exc:
        raise LicenseError('License key format is invalid.') from exc
    if not payload or not signature:
        raise LicenseError('License key format is invalid.')
    return payload, signature


def _load_claims(payload):
    try:
        claims = json.loads(_b64decode(payload).decode('utf-8'))
    except (ValueError, json.JSONDecodeError) as exc:
        raise LicenseError('License payload is invalid.') from exc

    required_fields = {'customer', 'expires_on', 'fingerprint'}
    if not required_fields.issubset(claims):
        raise LicenseError('License payload is incomplete.')
    return claims


def _sign(payload, secret):
    digest = hmac.new(
        secret.encode('utf-8'),
        payload.encode('ascii'),
        hashlib.sha256,
    ).digest()
    return _b64encode(digest)


def _json_dumps(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True).encode('utf-8')


def _b64encode(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _b64decode(value):
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _read_first_existing(*paths):
    for path in paths:
        try:
            value = path.read_text(encoding='utf-8').strip()
        except OSError:
            continue
        if value:
            return value
    return ''
