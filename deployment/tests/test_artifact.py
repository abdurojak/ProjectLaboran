import tempfile
import unittest
from pathlib import Path, PurePosixPath

from deployment.artifact import inspect_release_tree, load_protected_modules


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

    def test_accepts_native_extension_without_protected_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            release_root = Path(temp_dir)
            self._write_extension(release_root)

            errors = inspect_release_tree(release_root, self.protected)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
