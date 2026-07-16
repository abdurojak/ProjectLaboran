"""Generate a keypair with compensating rollback, not cross-path crash atomicity.

The two outputs may live in different directories, so no filesystem primitive can
commit them crash-atomically. Lock files serialize cooperating command instances;
publication identity checks protect rollback from unrelated external writers.
"""

import os
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.core.management.base import BaseCommand, CommandError


def _unlink_artifact(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        return None
    except BaseException:
        return Path(path)
    return None


def _cleanup_staged_file(path):
    failed_path = _unlink_artifact(path)
    if failed_path is None:
        return None

    try:
        os.truncate(path, 0)
    except BaseException:
        pass
    try:
        os.chmod(path, 0)
    except BaseException:
        pass
    return failed_path


def _stage_write(path, content, *, mode):
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

        try:
            os.chmod(temporary_name, mode)
        except NotImplementedError:
            pass

        return temporary_name
    except BaseException as exc:
        failed_path = _cleanup_staged_file(temporary_name)
        if failed_path is not None:
            raise CommandError(
                f'Unable to clean staged license key file: {failed_path}'
            ) from exc
        raise


def _reserve_artifact(path, suffix):
    descriptor, artifact_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f'.{path.name}.',
        suffix=suffix,
    )
    try:
        os.close(descriptor)
    except BaseException as exc:
        failed_path = _unlink_artifact(artifact_name)
        if failed_path is not None:
            raise CommandError(
                f'Unable to clean reserved recovery file: {failed_path}'
            ) from exc
        raise
    return artifact_name


def _reserve_backup(path):
    return _reserve_artifact(path, '.bak')


def _lock_path(path):
    return path.with_name(f'.{path.name}.lock')


def _publication_state(path, expected_stat, expected_content):
    try:
        current_stat = os.stat(path)
    except FileNotFoundError:
        return 'missing'
    except BaseException:
        return 'unknown'

    if not os.path.samestat(current_stat, expected_stat):
        return 'foreign'

    try:
        current_content = path.read_bytes()
    except BaseException:
        return 'unknown'
    return 'owned' if current_content == expected_content else 'foreign'


def _unique_paths(paths):
    return list(dict.fromkeys(Path(path) for path in paths))


def _path_list(paths):
    return ', '.join(str(path) for path in _unique_paths(paths))


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
        except OSError as exc:
            raise CommandError('Unable to inspect license keypair output files.') from exc

        if private_key_path == public_key_path:
            raise CommandError('Private and public outputs must be different files.')

        output_paths = (private_key_path, public_key_path)
        lock_paths = sorted(
            (_lock_path(path) for path in output_paths),
            key=lambda path: os.path.normcase(str(path)),
        )
        acquired_locks = []
        staged_outputs = []
        backup_paths = []
        backups = []
        published = []
        primary_error = None
        rollback_problems = []
        recovery_paths = []

        try:
            for path in output_paths:
                path.parent.mkdir(parents=True, exist_ok=True)

            for lock_path in lock_paths:
                try:
                    descriptor = os.open(
                        lock_path,
                        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                        0o600,
                    )
                except OSError as exc:
                    raise CommandError(
                        f'Unable to acquire license keypair lock: {lock_path}'
                    ) from exc
                acquired_locks.append(lock_path)
                os.close(descriptor)

            try:
                private_exists = private_key_path.exists()
                public_exists = public_key_path.exists()
                same_output = (
                    private_exists
                    and public_exists
                    and os.path.samefile(private_key_path, public_key_path)
                )
            except OSError as exc:
                raise CommandError(
                    'Unable to inspect license keypair output files.'
                ) from exc

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

            staged_private = _stage_write(private_key_path, private_pem, mode=0o600)
            staged_outputs.append(
                (staged_private, private_key_path, private_pem, 0o600)
            )
            staged_public = _stage_write(public_key_path, public_module, mode=0o644)
            staged_outputs.append(
                (staged_public, public_key_path, public_module, 0o644)
            )

            if options['force']:
                for output_path in existing_paths:
                    original_stat = os.stat(output_path)
                    original_content = output_path.read_bytes()
                    backup_path = _reserve_backup(output_path)
                    backup_paths.append(backup_path)
                    backups.append(
                        (
                            backup_path,
                            output_path,
                            original_stat,
                            original_content,
                        )
                    )
                    os.replace(output_path, backup_path)

            for staged_path, output_path, content, mode in staged_outputs:
                expected_stat = os.stat(staged_path)
                published.append((output_path, expected_stat, content))
                if options['force']:
                    os.replace(staged_path, output_path)
                else:
                    os.link(staged_path, output_path)
                try:
                    os.chmod(output_path, mode)
                except NotImplementedError:
                    pass
                if not options['force']:
                    os.unlink(staged_path)
        except BaseException as exc:
            primary_error = exc

            unsafe_targets = set()
            for output_path, expected_stat, content in reversed(published):
                try:
                    rollback_path = _reserve_artifact(output_path, '.rollback')
                except BaseException:
                    unsafe_targets.add(output_path)
                    rollback_problems.append(output_path)
                    continue

                try:
                    os.replace(output_path, rollback_path)
                except FileNotFoundError:
                    failed_path = _unlink_artifact(rollback_path)
                    if failed_path is not None:
                        recovery_paths.append(failed_path)
                        rollback_problems.append(output_path)
                    continue
                except BaseException:
                    failed_path = _unlink_artifact(rollback_path)
                    if failed_path is not None:
                        recovery_paths.append(failed_path)
                    unsafe_targets.add(output_path)
                    rollback_problems.append(output_path)
                    continue

                state = _publication_state(
                    Path(rollback_path),
                    expected_stat,
                    content,
                )
                if state == 'owned':
                    failed_path = _cleanup_staged_file(rollback_path)
                    if failed_path is not None:
                        recovery_paths.append(failed_path)
                        rollback_problems.append(output_path)
                    continue

                try:
                    os.link(rollback_path, output_path)
                except BaseException:
                    recovery_paths.append(rollback_path)
                    unsafe_targets.add(output_path)
                    rollback_problems.append(output_path)
                    continue

                failed_path = _unlink_artifact(rollback_path)
                if failed_path is not None:
                    recovery_paths.append(failed_path)
                    rollback_problems.append(output_path)
                unsafe_targets.add(output_path)

            for (
                backup_path,
                output_path,
                original_stat,
                original_content,
            ) in reversed(backups):
                backup_state = _publication_state(
                    Path(backup_path),
                    original_stat,
                    original_content,
                )
                if backup_state == 'foreign':
                    failed_path = _unlink_artifact(backup_path)
                    if failed_path is not None:
                        recovery_paths.append(failed_path)
                        rollback_problems.append(output_path)
                    continue
                if backup_state != 'owned':
                    recovery_paths.append(backup_path)
                    rollback_problems.append(output_path)
                    continue
                if output_path in unsafe_targets:
                    recovery_paths.append(backup_path)
                    continue
                try:
                    os.link(backup_path, output_path)
                except BaseException:
                    recovery_paths.append(backup_path)
                    rollback_problems.append(output_path)
                    continue
                failed_path = _unlink_artifact(backup_path)
                if failed_path is not None:
                    recovery_paths.append(failed_path)
                    rollback_problems.append(output_path)

        journaled_backups = {backup_path for backup_path, _, _, _ in backups}
        cleanup_paths = []

        if primary_error is None:
            for backup_path in backup_paths:
                failed_path = _unlink_artifact(backup_path)
                if failed_path is not None:
                    cleanup_paths.append(failed_path)
        else:
            for backup_path in backup_paths:
                if backup_path not in journaled_backups:
                    failed_path = _unlink_artifact(backup_path)
                    if failed_path is not None:
                        cleanup_paths.append(failed_path)

        for staged_path, _, _, _ in staged_outputs:
            failed_path = _cleanup_staged_file(staged_path)
            if failed_path is not None:
                cleanup_paths.append(failed_path)

        for lock_path in reversed(acquired_locks):
            failed_path = _unlink_artifact(lock_path)
            if failed_path is not None:
                cleanup_paths.append(failed_path)

        unresolved_paths = _unique_paths(
            recovery_paths + rollback_problems + cleanup_paths
        )
        if primary_error is not None:
            if unresolved_paths:
                preserved = _unique_paths(recovery_paths + cleanup_paths)
                message = 'Unable to complete safe rollback; recovery is required.'
                if preserved:
                    message += f' Preserved recovery paths: {_path_list(preserved)}.'
                affected = [
                    path for path in rollback_problems if Path(path) not in preserved
                ]
                if affected:
                    message += f' Affected paths: {_path_list(affected)}.'
                raise CommandError(message) from primary_error
            if isinstance(primary_error, CommandError):
                raise primary_error
            if isinstance(primary_error, OSError):
                raise CommandError(
                    'Unable to write license keypair output files.'
                ) from primary_error
            raise primary_error.with_traceback(primary_error.__traceback__)

        if cleanup_paths:
            raise CommandError(
                'License keypair was published, but cleanup failed. '
                f'Preserved recovery paths: {_path_list(cleanup_paths)}.'
            )
