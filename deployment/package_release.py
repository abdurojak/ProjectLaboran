import argparse
import hashlib
import io
import json
import os
import re
import tarfile
import tempfile
from pathlib import Path


ARCHIVE_NAME = "projectlaboran.protected.tar.gz"
MANIFEST_NAME = "deployment-manifest.json"
SIGNATURE_NAME = "deployment-manifest.sig"
EXPECTED_REPOSITORY = "abdurojak/ProjectLaboran"
EXPECTED_REF = "refs/heads/main"
EXPECTED_WORKFLOW = ".github/workflows/test-runner.yml"
MANIFEST_KEYS = {
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
}


def _sha256(value):
    digest = hashlib.sha256()
    if isinstance(value, (bytes, bytearray)):
        digest.update(value)
    else:
        with Path(value).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _positive_integer(name, value):
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def build_manifest(
    archive,
    *,
    repository,
    run_attempt,
    run_id,
    run_number,
    source_ref,
    source_sha,
    workflow,
):
    for name, value in (
        ("run_attempt", run_attempt),
        ("run_id", run_id),
        ("run_number", run_number),
    ):
        _positive_integer(name, value)
    if repository != EXPECTED_REPOSITORY:
        raise ValueError("repository claim is not trusted")
    if source_ref != EXPECTED_REF:
        raise ValueError("source_ref claim is not trusted")
    if workflow != EXPECTED_WORKFLOW:
        raise ValueError("workflow claim is not trusted")
    if type(source_sha) is not str or re.fullmatch(r"[0-9a-f]{40}", source_sha) is None:
        raise ValueError("source_sha must be 40 lowercase hexadecimal characters")

    payload = {
        "archive_name": ARCHIVE_NAME,
        "archive_sha256": _sha256(archive),
        "repository": repository,
        "run_attempt": run_attempt,
        "run_id": run_id,
        "run_number": run_number,
        "source_ref": source_ref,
        "source_sha": source_sha,
        "version": 1,
        "workflow": workflow,
    }
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")


def _validate_manifest(manifest, archive):
    if len(manifest) > 4096 or not manifest.endswith(b"\n"):
        raise ValueError("manifest is not canonical")
    try:
        payload = json.loads(manifest.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("manifest is not valid canonical ASCII JSON") from error
    canonical = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")
    if canonical != manifest or type(payload) is not dict or set(payload) != MANIFEST_KEYS:
        raise ValueError("manifest schema or canonical encoding is invalid")
    expected = build_manifest(
        archive,
        repository=payload["repository"],
        run_attempt=payload["run_attempt"],
        run_id=payload["run_id"],
        run_number=payload["run_number"],
        source_ref=payload["source_ref"],
        source_sha=payload["source_sha"],
        workflow=payload["workflow"],
    )
    if expected != manifest:
        raise ValueError("manifest does not match the protected archive")


def _tar_info(name, size):
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = 0o600
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.pax_headers = {}
    info.tobuf(format=tarfile.USTAR_FORMAT, encoding="ascii", errors="strict")
    return info


def write_envelope(archive, manifest, signature, output):
    archive = Path(archive)
    manifest = Path(manifest)
    signature = Path(signature)
    output = Path(output)
    if not archive.is_file() or not manifest.is_file() or not signature.is_file():
        raise ValueError("archive, manifest, and signature must be regular files")
    manifest_bytes = manifest.read_bytes()
    signature_bytes = signature.read_bytes()
    if len(signature_bytes) != 64:
        raise ValueError("Ed25519 signature must be exactly 64 bytes")
    _validate_manifest(manifest_bytes, archive)

    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as raw_output:
            with tarfile.open(
                fileobj=raw_output,
                mode="w|",
                format=tarfile.USTAR_FORMAT,
                encoding="ascii",
                errors="strict",
            ) as envelope:
                with archive.open("rb") as archive_source:
                    envelope.addfile(
                        _tar_info(ARCHIVE_NAME, archive.stat().st_size), archive_source
                    )
                envelope.addfile(_tar_info(MANIFEST_NAME, len(manifest_bytes)), io.BytesIO(manifest_bytes))
                envelope.addfile(_tar_info(SIGNATURE_NAME, 64), io.BytesIO(signature_bytes))
            raw_output.flush()
            os.fsync(raw_output.fileno())
        os.replace(temporary, output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _parser():
    parser = argparse.ArgumentParser(description="Create a signed deployment envelope.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    manifest = subparsers.add_parser("manifest")
    manifest.add_argument("--archive", required=True)
    manifest.add_argument("--output", required=True)
    manifest.add_argument("--repository", required=True)
    manifest.add_argument("--run-attempt", required=True, type=int)
    manifest.add_argument("--run-id", required=True, type=int)
    manifest.add_argument("--run-number", required=True, type=int)
    manifest.add_argument("--source-ref", required=True)
    manifest.add_argument("--source-sha", required=True)
    manifest.add_argument("--workflow", required=True)
    envelope = subparsers.add_parser("envelope")
    envelope.add_argument("--archive", required=True)
    envelope.add_argument("--manifest", required=True)
    envelope.add_argument("--signature", required=True)
    envelope.add_argument("--output", required=True)
    return parser


def main():
    args = _parser().parse_args()
    if args.command == "manifest":
        content = build_manifest(
            Path(args.archive),
            repository=args.repository,
            run_attempt=args.run_attempt,
            run_id=args.run_id,
            run_number=args.run_number,
            source_ref=args.source_ref,
            source_sha=args.source_sha,
            workflow=args.workflow,
        )
        Path(args.output).write_bytes(content)
    else:
        write_envelope(args.archive, args.manifest, args.signature, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
