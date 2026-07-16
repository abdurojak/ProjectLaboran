import base64
import binascii
import json
import os
from datetime import date
from pathlib import Path

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from django.core.exceptions import ImproperlyConfigured


class LicenseError(ImproperlyConfigured):
    pass


def build_license_key(customer, fingerprint, expires_on, private_key_pem):
    private_key = _load_private_key(private_key_pem)
    claims = {
        'customer': customer,
        'expires_on': expires_on.isoformat(),
        'fingerprint': fingerprint,
        'version': 2,
    }
    payload = _b64encode(_json_dumps(claims))
    signature = _b64encode(private_key.sign(payload.encode('ascii')))
    return f'{payload}.{signature}'


def validate_license_key(license_key, fingerprint, public_key_pem, today=None):
    if not license_key:
        raise LicenseError('License key is required.')

    payload, signature = _split_license_key(license_key)
    public_key = _load_public_key(public_key_pem)

    try:
        signature_bytes = _b64decode(signature)
        public_key.verify(signature_bytes, payload.encode('ascii'))
    except (InvalidSignature, UnicodeEncodeError, ValueError) as exc:
        raise LicenseError('License signature is invalid.') from exc

    claims = _load_claims(payload)
    if claims['version'] != 2:
        raise LicenseError('License version is unsupported.')
    if claims['fingerprint'] != fingerprint:
        raise LicenseError('License fingerprint does not match this server.')

    try:
        expires_on = date.fromisoformat(claims['expires_on'])
    except (TypeError, ValueError) as exc:
        raise LicenseError('License expiration date is invalid.') from exc
    if claims['expires_on'] != expires_on.isoformat():
        raise LicenseError('License expiration date must use YYYY-MM-DD format.')
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
    from apps.core.license_public_key import PUBLIC_KEY_PEM

    validate_license_key(
        os.getenv('LABHUB_LICENSE_KEY', '').strip(),
        fingerprint=get_server_fingerprint(),
        public_key_pem=PUBLIC_KEY_PEM,
    )


def _load_private_key(private_key_pem):
    if not private_key_pem:
        raise LicenseError('License private key is required.')
    try:
        if isinstance(private_key_pem, str):
            private_key_pem = private_key_pem.encode('ascii')
        private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    except (TypeError, ValueError, UnsupportedAlgorithm) as exc:
        raise LicenseError('License private key is invalid.') from exc
    if not isinstance(private_key, Ed25519PrivateKey):
        raise LicenseError('License signing requires an Ed25519 private key.')
    return private_key


def _load_public_key(public_key_pem):
    if not public_key_pem:
        raise LicenseError('License public key is required.')
    if isinstance(public_key_pem, str):
        public_key_pem = public_key_pem.encode('utf-8')
    try:
        public_key = serialization.load_pem_public_key(public_key_pem)
    except (TypeError, ValueError, UnsupportedAlgorithm) as exc:
        raise LicenseError('License public key is invalid.') from exc
    if not isinstance(public_key, Ed25519PublicKey):
        raise LicenseError('License verification requires an Ed25519 public key.')
    return public_key


def _split_license_key(license_key):
    if not isinstance(license_key, str):
        raise LicenseError('License key format is invalid.')
    parts = license_key.split('.')
    if len(parts) != 2 or not all(parts):
        raise LicenseError('License key format is invalid.')
    return parts


def _load_claims(payload):
    try:
        payload_bytes = _b64decode(payload)
        claims = json.loads(payload_bytes.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise LicenseError('License payload is invalid.') from exc

    if not isinstance(claims, dict):
        raise LicenseError('License payload must be an object.')
    if _json_dumps(claims) != payload_bytes:
        raise LicenseError('License payload JSON is not canonical.')

    required_fields = {'customer', 'expires_on', 'fingerprint', 'version'}
    if not required_fields.issubset(claims):
        raise LicenseError('License payload is incomplete.')
    if not isinstance(claims['customer'], str):
        raise LicenseError('License payload customer is invalid.')
    if not isinstance(claims['expires_on'], str):
        raise LicenseError('License payload expiration date is invalid.')
    if not isinstance(claims['fingerprint'], str):
        raise LicenseError('License payload fingerprint is invalid.')
    if not isinstance(claims['version'], int):
        raise LicenseError('License payload version is invalid.')
    return claims


def _json_dumps(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True).encode('utf-8')


def _b64encode(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _b64decode(value):
    try:
        encoded = value.encode('ascii')
        padding = b'=' * (-len(encoded) % 4)
        decoded = base64.b64decode(encoded + padding, altchars=b'-_', validate=True)
        if value != _b64encode(decoded):
            raise ValueError('Base64url value is not canonical.')
        return decoded
    except (AttributeError, UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise ValueError('Invalid base64url value.') from exc


def _read_first_existing(*paths):
    for path in paths:
        try:
            value = path.read_text(encoding='utf-8').strip()
        except OSError:
            continue
        if value:
            return value
    return ''
