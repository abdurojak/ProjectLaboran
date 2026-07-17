import io
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from deployment import build_protected_artifact as builder
from deployment.artifact import inspect_release_tree, load_protected_modules
from deployment.verify_protected_artifact import _extract_archive, verify_artifact


class LoadProtectedModulesTests(unittest.TestCase):
    def test_returns_normalized_posix_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            allowlist = Path(temp_dir) / "protected_modules.txt"
            allowlist.write_text(
                "\napps/core/./licensing.py\n"
                "apps\\mobile_api\\jwt_service.py\n",
                encoding="utf-8",
            )

            protected = load_protected_modules(allowlist)

        self.assertEqual(
            protected,
            [
                PurePosixPath("apps/core/licensing.py"),
                PurePosixPath("apps/mobile_api/jwt_service.py"),
            ],
        )

    def test_rejects_absolute_paths(self):
        invalid_entries = ("/apps/core/licensing.py", "C:/apps/core/licensing.py")

        for entry in invalid_entries:
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as temp_dir:
                allowlist = Path(temp_dir) / "protected_modules.txt"
                allowlist.write_text(f"{entry}\n", encoding="utf-8")

                with self.assertRaises(ValueError):
                    load_protected_modules(allowlist)

    def test_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            allowlist = Path(temp_dir) / "protected_modules.txt"
            allowlist.write_text("apps/../secrets.py\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_protected_modules(allowlist)


class InspectReleaseTreeTests(unittest.TestCase):
    protected = [PurePosixPath("apps/core/licensing.py")]

    def _write_extension(self, release_root):
        extension = (
            Path(release_root)
            / "apps/core/licensing.cpython-311-x86_64-linux-gnu.so"
        )
        extension.parent.mkdir(parents=True, exist_ok=True)
        extension.write_bytes(b"compiled")

    def test_rejects_forbidden_names_recursively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            release_root = Path(temp_dir)
            self._write_extension(release_root)
            for relative_path in (
                ".env",
                "config/.env.backup",
                "nested/.git/config",
                "nested/deeper/.secrets/key",
            ):
                path = release_root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.name in {".git", ".secrets"}:
                    path.mkdir()
                else:
                    path.write_text("secret", encoding="utf-8")

            errors = inspect_release_tree(release_root, self.protected)

        for forbidden_name in (".env", ".env.backup", ".git", ".secrets"):
            with self.subTest(forbidden_name=forbidden_name):
                self.assertTrue(
                    any(forbidden_name in error for error in errors),
                    errors,
                )

    def test_rejects_private_pem_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            release_root = Path(temp_dir)
            self._write_extension(release_root)
            private_key = release_root / "config/private.pem"
            private_key.parent.mkdir(parents=True, exist_ok=True)
            private_key.write_text("private key", encoding="utf-8")

            errors = inspect_release_tree(release_root, self.protected)

        self.assertTrue(any("config/private.pem" in error for error in errors), errors)

    def test_rejects_protected_python_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            release_root = Path(temp_dir)
            self._write_extension(release_root)
            source = release_root / "apps/core/licensing.py"
            source.write_text("SECRET = True\n", encoding="utf-8")

            errors = inspect_release_tree(release_root, self.protected)

        self.assertTrue(any("protected source" in error.lower() for error in errors), errors)

    def test_rejects_missing_native_extension(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            release_root = Path(temp_dir)
            release_root.mkdir(exist_ok=True)

            errors = inspect_release_tree(release_root, self.protected)

        self.assertTrue(any("native extension" in error.lower() for error in errors), errors)

    def test_rejects_directory_named_like_native_extension(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            release_root = Path(temp_dir)
            fake_extension = release_root / "apps/core/licensing.fake.so"
            fake_extension.mkdir(parents=True)

            errors = inspect_release_tree(release_root, self.protected)

        self.assertTrue(any("native extension" in error.lower() for error in errors), errors)

    def test_accepts_native_extension_without_protected_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            release_root = Path(temp_dir)
            self._write_extension(release_root)

            errors = inspect_release_tree(release_root, self.protected)

        self.assertEqual(errors, [])

    def test_rejects_sensitive_metadata_license_and_key_material(self):
        sensitive_paths = (
            ".env.windows-backup",
            ".gitignore",
            ".github/workflow.yml",
            ".codex-remote-attachments/payload.bin",
            "tmp/surat-reference/notes.txt",
            "config/labhub.env",
            "config/license.key",
            "config/customer.license",
            "config/private.pem",
            "config/server.key",
            "config/certificate.crt",
            "config/server.cert",
            "config/identity.p12",
            "config/id_rsa",
            "config/private.ppk",
            "config/private_key",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            release_root = Path(temp_dir)
            self._write_extension(release_root)
            for relative_path in sensitive_paths:
                path = release_root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"sensitive")

            errors = inspect_release_tree(release_root, self.protected)

        for relative_path in sensitive_paths:
            with self.subTest(relative_path=relative_path):
                self.assertTrue(
                    any(relative_path in error for error in errors),
                    errors,
                )


class SafeArchiveExtractionTests(unittest.TestCase):
    def _write_archive(self, archive_path, name, member_type=tarfile.REGTYPE):
        payload = b"archive payload"
        with tarfile.open(archive_path, "w:gz") as archive:
            member = tarfile.TarInfo(name)
            member.type = member_type
            if member_type in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
                member.linkname = "target"
                archive.addfile(member)
            else:
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))

    def test_rejects_windows_drive_relative_member_before_extractall(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive_path = root / "unsafe.tar.gz"
            destination = root / "extract"
            destination.mkdir()
            self._write_archive(archive_path, "C:escape.txt")

            with patch.object(tarfile.TarFile, "extractall") as extractall:
                with self.assertRaisesRegex(ValueError, "Unsafe archive path"):
                    _extract_archive(archive_path, destination)

            extractall.assert_not_called()

    def test_rejects_absolute_and_traversal_members(self):
        for member_name in ("/absolute.txt", "../escape.txt", "safe/../../escape.txt"):
            with self.subTest(
                member_name=member_name
            ), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                archive_path = root / "unsafe.tar.gz"
                destination = root / "extract"
                destination.mkdir()
                self._write_archive(archive_path, member_name)

                with self.assertRaisesRegex(ValueError, "Unsafe archive path"):
                    _extract_archive(archive_path, destination)

    def test_rejects_symbolic_and_hard_links(self):
        for member_type in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            with self.subTest(
                member_type=member_type
            ), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                archive_path = root / "unsafe.tar.gz"
                destination = root / "extract"
                destination.mkdir()
                self._write_archive(archive_path, "safe-link", member_type)

                with self.assertRaisesRegex(ValueError, "Unsafe archive link"):
                    _extract_archive(archive_path, destination)


class BuildPathValidationTests(unittest.TestCase):
    def test_rejects_staging_equal_to_or_ancestor_of_source_before_deletion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            source.mkdir()
            allowlist = root / "allowlist.txt"
            allowlist.write_text("", encoding="utf-8")
            output = root / "artifact.tar.gz"

            for staging in (source, root):
                with self.subTest(staging=staging), patch.object(
                    builder.shutil, "rmtree"
                ) as rmtree:
                    with self.assertRaisesRegex(ValueError, "staging"):
                        builder.build_artifact(source, staging, output, allowlist)

                    rmtree.assert_not_called()
                    self.assertTrue(source.is_dir())

    def test_rejects_unsafe_output_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            source.mkdir()
            staging = source / "build/protected/release"
            existing_directory = root / "existing-output"
            existing_directory.mkdir()
            source_file = source / "manage.py"
            source_file.write_text("application source", encoding="utf-8")

            unsafe_outputs = (
                source,
                staging,
                source_file,
                staging.parent,
                staging / "artifact.tar.gz",
                existing_directory,
            )
            for output in unsafe_outputs:
                with self.subTest(output=output):
                    with self.assertRaisesRegex(ValueError, "output"):
                        builder._validate_build_paths(source, staging, output)

    def test_accepts_dedicated_build_and_dist_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()

            resolved_paths = builder._validate_build_paths(
                source,
                source / "build/protected/release",
                source / "dist/protected/artifact.tar.gz",
            )

        self.assertEqual(resolved_paths[0], source.resolve())

    def test_resolves_paths_before_comparing_them(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            source.mkdir()
            equivalent_staging = source / "nested/.."

            with self.assertRaisesRegex(ValueError, "staging"):
                builder._validate_build_paths(
                    source,
                    equivalent_staging,
                    root / "artifact.tar.gz",
                )

    def test_rejects_staging_inside_application_source_tree(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()

            with self.assertRaisesRegex(ValueError, "staging"):
                builder._validate_build_paths(
                    source,
                    source / "apps",
                    source / "dist/protected/artifact.tar.gz",
                )


class BuilderIgnorePolicyTests(unittest.TestCase):
    def test_copytree_filters_sensitive_files_and_preserves_application_files(self):
        sensitive_names = (
            ".env.windows-backup",
            ".gitignore",
            ".github",
            ".secrets",
            ".codex-remote-attachments",
            "tmp",
            "labhub.env",
            "license.key",
            "customer.license",
            "private.pem",
            "server.key",
            "certificate.crt",
            "server.cert",
            "identity.p12",
            "id_ed25519",
            "private.ppk",
            "private_key",
        )
        application_names = (
            "apps",
            "project_laboran",
            "manage.py",
            "requirements.txt",
            "license_public_key.py",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            destination = root / "release"
            source.mkdir()
            for name in sensitive_names + application_names:
                path = source / name
                if "." not in name and name not in {"tmp", "id_ed25519"}:
                    path.mkdir()
                    (path / "content.txt").write_text("content", encoding="utf-8")
                elif name in {
                    ".github",
                    ".secrets",
                    ".codex-remote-attachments",
                    "tmp",
                }:
                    path.mkdir()
                    (path / "content.txt").write_text("content", encoding="utf-8")
                else:
                    path.write_text("content", encoding="utf-8")

            shutil.copytree(source, destination, ignore=builder._ignore_source_entries)

            copied_names = {path.name for path in destination.iterdir()}

        self.assertTrue(set(sensitive_names).isdisjoint(copied_names), copied_names)
        self.assertTrue(set(application_names).issubset(copied_names), copied_names)


class ArchiveCreationTests(unittest.TestCase):
    def test_writes_release_contents_at_archive_root_and_verifies_them(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            staging = root / "release"
            extension = (
                staging / "apps/core/licensing.cpython-311-x86_64-linux-gnu.so"
            )
            extension.parent.mkdir(parents=True)
            extension.write_bytes(b"compiled")
            (staging / "manage.py").write_text("application", encoding="utf-8")
            output = root / "artifact.tar.gz"
            allowlist = root / "allowlist.txt"
            allowlist.write_text("apps/core/licensing.py\n", encoding="utf-8")

            builder._write_archive(staging, output)

            with tarfile.open(output, "r:gz") as archive:
                names = set(archive.getnames())
            errors = verify_artifact(output, allowlist)

        self.assertIn("manage.py", names)
        self.assertIn(
            "apps/core/licensing.cpython-311-x86_64-linux-gnu.so",
            names,
        )
        self.assertFalse(
            any(name == "release" or name.startswith("release/") for name in names)
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
