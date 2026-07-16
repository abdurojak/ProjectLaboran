import os
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.core.management.base import BaseCommand, CommandError


def _stage_write(path, content, *, mode=None):
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f'.{path.name}.',
        suffix='.tmp',
    )
    try:
        with os.fdopen(descriptor, 'wb') as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        if mode is not None:
            try:
                os.chmod(temporary_name, mode)
            except NotImplementedError:
                pass

        return temporary_name
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


class Command(BaseCommand):
    help = 'Generate the LabHub owner Ed25519 license keypair.'

    def add_arguments(self, parser):
        parser.add_argument('--private-key-file', required=True)
        parser.add_argument('--public-key-module', required=True)
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        private_key_path = Path(options['private_key_file'])
        public_key_path = Path(options['public_key_module'])

        try:
            existing_paths = [
                path for path in (private_key_path, public_key_path) if path.exists()
            ]
        except OSError as exc:
            raise CommandError('Unable to inspect license keypair output files.') from exc

        if existing_paths and not options['force']:
            raise CommandError(f'Output already exists: {existing_paths[0]}')

        private_key = Ed25519PrivateKey.generate()
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        public_module = f'PUBLIC_KEY_PEM = {public_pem!r}\n'.encode('ascii')

        staged_paths = []
        try:
            private_key_path.parent.mkdir(parents=True, exist_ok=True)
            public_key_path.parent.mkdir(parents=True, exist_ok=True)
            staged_private = _stage_write(private_key_path, private_pem, mode=0o600)
            staged_paths.append(staged_private)
            staged_public = _stage_write(public_key_path, public_module)
            staged_paths.append(staged_public)
            os.replace(staged_private, private_key_path)
            os.replace(staged_public, public_key_path)
        except OSError as exc:
            raise CommandError('Unable to write license keypair output files.') from exc
        finally:
            for staged_path in staged_paths:
                try:
                    os.unlink(staged_path)
                except FileNotFoundError:
                    pass
