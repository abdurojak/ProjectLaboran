import hashlib
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from deployment.package_release import build_manifest, write_envelope


VALID_CLAIMS = {
    "repository": "abdurojak/ProjectLaboran",
    "run_attempt": 1,
    "run_id": 123456,
    "run_number": 42,
    "source_ref": "refs/heads/main",
    "source_sha": "a" * 40,
    "workflow": ".github/workflows/test-runner.yml",
}


class ManifestTests(unittest.TestCase):
    def test_builds_exact_canonical_manifest(self):
        archive = b"protected release"

        manifest = build_manifest(archive, **VALID_CLAIMS)
        payload = json.loads(manifest)

        self.assertTrue(manifest.endswith(b"\n"))
        self.assertEqual(manifest.count(b"\n"), 1)
        self.assertEqual(
            manifest,
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii")
            + b"\n",
        )
        self.assertEqual(
            set(payload),
            {
                "archive_name",
                "archive_sha256",
                "repository",
                "run_attempt",
                "run_id",
                "run_number",
                "source_ref",
                "source_sha",
                "version",
                "workflow",
            },
        )
        self.assertEqual(payload["archive_name"], "projectlaboran.protected.tar.gz")
        self.assertEqual(payload["archive_sha256"], hashlib.sha256(archive).hexdigest())
        self.assertEqual(payload["version"], 1)

    def test_rejects_invalid_or_boolean_run_claims(self):
        for field in ("run_attempt", "run_id", "run_number"):
            for invalid in (True, False, 0, -1, "1"):
                with self.subTest(field=field, invalid=invalid):
                    claims = dict(VALID_CLAIMS)
                    claims[field] = invalid
                    with self.assertRaises(ValueError):
                        build_manifest(b"archive", **claims)

    def test_rejects_untrusted_identity_claims(self):
        invalid_claims = {
            "repository": "attacker/fork",
            "source_ref": "refs/heads/feature",
            "source_sha": "A" * 40,
            "workflow": ".github/workflows/other.yml",
        }
        for field, invalid in invalid_claims.items():
            with self.subTest(field=field):
                claims = dict(VALID_CLAIMS)
                claims[field] = invalid
                with self.assertRaises(ValueError):
                    build_manifest(b"archive", **claims)


class EnvelopeTests(unittest.TestCase):
    def test_writes_exact_deterministic_ustar_envelope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = root / "projectlaboran.protected.tar.gz"
            manifest = root / "deployment-manifest.json"
            signature = root / "deployment-manifest.sig"
            first = root / "first.tar"
            second = root / "second.tar"
            archive.write_bytes(b"archive")
            manifest.write_bytes(build_manifest(b"archive", **VALID_CLAIMS))
            signature.write_bytes(b"s" * 64)

            write_envelope(archive, manifest, signature, first)
            write_envelope(archive, manifest, signature, second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first, "r:") as envelope:
                members = envelope.getmembers()
                self.assertEqual(
                    [member.name for member in members],
                    [
                        "projectlaboran.protected.tar.gz",
                        "deployment-manifest.json",
                        "deployment-manifest.sig",
                    ],
                )
                self.assertTrue(all(member.isfile() for member in members))
                self.assertTrue(all(member.pax_headers == {} for member in members))
                self.assertTrue(all(member.uid == 0 and member.gid == 0 for member in members))

    def test_rejects_wrong_signature_size(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = root / "projectlaboran.protected.tar.gz"
            manifest = root / "deployment-manifest.json"
            signature = root / "deployment-manifest.sig"
            archive.write_bytes(b"archive")
            manifest.write_bytes(build_manifest(b"archive", **VALID_CLAIMS))
            signature.write_bytes(b"s" * 63)

            with self.assertRaisesRegex(ValueError, "64 bytes"):
                write_envelope(archive, manifest, signature, root / "envelope.tar")

    def test_rejects_canonical_manifest_with_untrusted_claim(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = root / "projectlaboran.protected.tar.gz"
            manifest = root / "deployment-manifest.json"
            signature = root / "deployment-manifest.sig"
            archive.write_bytes(b"archive")
            payload = json.loads(build_manifest(b"archive", **VALID_CLAIMS))
            payload["repository"] = "attacker/fork"
            manifest.write_bytes(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode("ascii")
                + b"\n"
            )
            signature.write_bytes(b"s" * 64)

            with self.assertRaisesRegex(ValueError, "trusted"):
                write_envelope(archive, manifest, signature, root / "envelope.tar")


class WorkflowContractTests(unittest.TestCase):
    def test_workflow_is_manual_signed_artifact_deployment(self):
        workflow = (
            Path(__file__).parents[2] / ".github/workflows/test-runner.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertIn("PRODUCTION_ARTIFACT_SIGNING_PRIVATE_KEY", workflow)
        self.assertIn("docker run --rm", workflow)
        self.assertNotIn("    container:\n", workflow)
        self.assertIn("deployment-manifest.sig", workflow)
        self.assertIn("package_release.py", workflow)
        self.assertIn("projectlaboran.deploy.tar", workflow)
        self.assertNotIn("git pull", workflow)
        self.assertNotIn("manage.py migrate", workflow)
        self.assertNotIn("systemctl restart", workflow)
        self.assertEqual(
            workflow.count(
                "sudo -n /usr/local/sbin/projectlaboran-deploy "
                "/home/admin/LabTif/incoming/projectlaboran.deploy.tar"
            ),
            1,
        )

    def test_self_hosted_job_does_not_checkout_or_receive_signing_secret(self):
        workflow = (
            Path(__file__).parents[2] / ".github/workflows/test-runner.yml"
        ).read_text(encoding="utf-8")
        deploy_job = workflow.split("  deploy:", 1)[1]

        self.assertIn("runs-on: [self-hosted, linux, x64]", deploy_job)
        self.assertNotIn("actions/checkout", deploy_job)
        self.assertNotIn("PRODUCTION_ARTIFACT_SIGNING_PRIVATE_KEY", deploy_job)


if __name__ == "__main__":
    unittest.main()
