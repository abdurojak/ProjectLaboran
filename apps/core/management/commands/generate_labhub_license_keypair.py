import os
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.core.management.base import BaseCommand, CommandError


def _best_effort_unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


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
        _best_effort_unlink(temporary_name)
        raise


def _reserve_backup(path):
    descriptor, backup_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f'.{path.name}.',
        suffix='.bak',
    )
    try:
        os.close(descriptor)
    except OSError:
        _best_effort_unlink(backup_name)
        raise
    return backup_name


class Command(BaseCommand):
    help = 'Generate the LabHub owner Ed25519 license keypair.'

    def add_arguments(self, parser):
        parser.add_argument('--private-key-file', required=True)
        parser.add_argument('--public-key-module', required=True)
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        try:
            private_key_path = Path(options['private_key_file']).resolve()
            public_key_path = Path(options['public_key_module']).resolve()
            private_exists = private_key_path.exists()
            public_exists = public_key_path.exists()
            same_output = private_key_path == public_key_path
            if not same_output and private_exists and public_exists:
                same_output = os.path.samefile(private_key_path, public_key_path)
        except OSError as exc:
            raise CommandError('Unable to inspect license keypair output files.') from exc

        if same_output:
            raise CommandError('Private and public outputs must be different files.')

        existing_paths = [
            path
            for path, exists in (
                (private_key_path, private_exists),
                (public_key_path, public_exists),
            )
            if exists
        ]

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
        ).decode('ascii')
        public_module = f'PUBLIC_KEY_PEM = {public_pem!r}\n'.encode('ascii')

        staged_outputs = []
        backup_paths = []
        backups = []
        published_paths = []
        try:
            private_key_path.parent.mkdir(parents=True, exist_ok=True)
            public_key_path.parent.mkdir(parents=True, exist_ok=True)
            staged_private = _stage_write(private_key_path, private_pem, mode=0o600)
            staged_outputs.append((staged_private, private_key_path))
            staged_public = _stage_write(public_key_path, public_module)
            staged_outputs.append((staged_public, public_key_path))

            if options['force']:
                for output_path in existing_paths:
                    backup_path = _reserve_backup(output_path)
                    backup_paths.append(backup_path)
                    os.replace(output_path, backup_path)
                    backups.append((backup_path, output_path))

            for staged_path, output_path in staged_outputs:
                if options['force']:
                    os.replace(staged_path, output_path)
                else:
                    os.link(staged_path, output_path)
                published_paths.append(output_path)
                if not options['force']:
                    _best_effort_unlink(staged_path)
        except OSError as exc:
            for published_path in reversed(published_paths):
                _best_effort_unlink(published_path)
            for backup_path, output_path in reversed(backups):
                try:
                    os.replace(backup_path, output_path)
                except OSError:
                    pass
            raise CommandError('Unable to write license keypair output files.') from exc
        finally:
            for staged_path, _ in staged_outputs:
                _best_effort_unlink(staged_path)
            for backup_path in backup_paths:
                _best_effort_unlink(backup_path)
