# Production Code Protection Design

## Objective

Strengthen ProjectLaboran deployment without paid obfuscation software. Production licenses use asymmetric Ed25519 signatures, selected business modules are compiled with Cython, and AlmaLinux receives a production artifact instead of pulling the source repository.

This raises the effort required to copy, inspect, or reuse the application. It does not claim to defeat a determined administrator with root access, runtime debugging tools, and enough reverse-engineering time.

## Security Boundaries

- The Ed25519 private key exists only on the owner's laptop and is never committed, uploaded to GitHub, or copied to AlmaLinux.
- The application contains only the Ed25519 public key. Possessing the public key permits verification but not creation of a valid license.
- A license remains bound to `/etc/machine-id` and has an explicit expiration date.
- The repository remains private. GitHub-hosted Actions may read source during a build, but the AlmaLinux deploy job downloads only the resulting artifact.
- Root on AlmaLinux remains a trusted boundary. Root can inspect memory, patch binaries, replace services, or bypass application startup checks. The design provides deterrence and copy resistance, not absolute DRM.

## License Architecture

`apps/core/licensing.py` will replace HMAC-SHA256 signing with Ed25519 from the `cryptography` package.

The license format remains two URL-safe Base64 segments:

```text
base64url(canonical-json-claims).base64url(ed25519-signature)
```

Claims contain `customer`, `fingerprint`, `expires_on`, and `version`. The current format uses `version: 2`. Validation rejects malformed payloads, unsupported versions, invalid signatures, mismatched fingerprints, and expired licenses.

The public key is stored in a dedicated source module, `apps/core/license_public_key.py`, and compiled into the production extension alongside the validator. It is safe for the public key to exist in source history because it cannot sign licenses. Production no longer accepts `LABHUB_LICENSE_VERIFICATION_SECRET`.

Two management commands provide owner-side operations:

- `generate_labhub_license_keypair` writes an Ed25519 private key and prints the public key needed by the application. The private key file is created with restrictive permissions where supported and its conventional filename is ignored by Git.
- `generate_labhub_license` reads the private key from `LABHUB_LICENSE_PRIVATE_KEY_FILE` and emits a version 2 license.

There is no compatibility fallback to the HMAC license. During rollout, the owner creates a new version 2 license and updates the service environment before switching to the protected artifact.

## Cython Scope

Cython compiles selected modules into CPython extension files and the artifact omits their matching `.py` files. Initial scope favors modules with valuable business logic and stable import boundaries:

- `apps/core/licensing.py`
- `apps/core/license_public_key.py`
- `apps/mobile_api/jwt_service.py`
- `apps/asleb/services.py`
- `apps/peminjaman/services.py`
- `apps/pendaftaran_asleb/services.py`
- `apps/barang_tertinggal/services.py`

The build does not compile migrations, models, forms, views, settings, URLs, ASGI/WSGI entrypoints, management command wrappers, or tests. Django relies heavily on metadata, dynamic imports, and migration discovery in those files; keeping them as Python reduces deployment risk. More modules may be added only after passing production-equivalent tests.

The artifact contains each compiled extension under its original package path. Python imports the extension under the same module name, so application call sites do not change.

## Artifact Build

A dedicated build script owns file selection and packaging:

- `deployment/protected_modules.txt` is the allowlist of modules compiled by Cython.
- `deployment/build_protected_artifact.py` copies runtime files into a clean staging directory, compiles allowlisted modules in place, removes their source `.py` files, excludes tests, local environments, Git metadata, media, `.env` files, and owner private keys, then creates a compressed artifact.
- `deployment/verify_protected_artifact.py` rejects an artifact if a protected `.py` source file, private key, `.env`, or `.git` data is present and confirms every protected module has a matching extension binary.

The GitHub build job runs in the official `manylinux_2_28_x86_64` image. It selects the CPython ABI from repository variable `DEPLOY_PYTHON_ABI`, defaulting to `cp311-cp311`. Before rollout, this value must match the server venv reported by `python -c "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}')"`.

The workflow runs the Django test suite against source first, builds the artifact, runs artifact verification, starts Django checks from the staged artifact with license enforcement disabled, and uploads the archive to the same workflow run. A build failure prevents deployment.

## Deployment Flow

The existing workflow becomes two jobs:

1. `build` runs on a GitHub-hosted Linux runner, tests source, creates the Cython artifact, and uploads it.
2. `deploy` runs on the AlmaLinux self-hosted runner after `build` succeeds, downloads the artifact, extracts it to a versioned directory under `/home/admin/LabTif/releases`, updates `/home/admin/LabTif/current` atomically, installs requirements into `/home/admin/LabTif/production-venv`, runs migrations and `collectstatic`, and restarts `projectlaboran-daphne`.

The deploy job performs no checkout and no `git pull`. It never receives source for protected modules. Releases are owned by `admin`; the workflow retains the current and two previous releases for rollback.

One manual server change updates the systemd unit:

```ini
WorkingDirectory=/home/admin/LabTif/current
ExecStart=/home/admin/LabTif/production-venv/bin/python -m daphne -b 0.0.0.0 -p 8000 project_laboran.asgi:application
```

The license environment contains only:

```ini
LABHUB_LICENSE_ENFORCED=True
LABHUB_LICENSE_KEY=<version-2-license>
```

The old checkout at `/home/admin/LabTif/ProjectLaboran` is no longer used by systemd or deployment. Removing that historical checkout is a manual owner decision after the protected release is verified, because deletion is irreversible and cannot revoke copies already made.

## Failure Handling And Rollback

- Invalid or expired licenses stop Django startup with a specific `LicenseError` and appear in the systemd journal.
- Compilation, artifact inspection, Django checks, migrations, and static collection all use fail-fast behavior.
- The `current` symlink changes only after extraction and dependency installation succeed.
- If restart or health verification fails, the deploy script restores the previous `current` symlink and restarts Daphne on the previous release.
- A deployment lock prevents two self-hosted jobs from modifying releases concurrently.
- GitHub Actions uses workflow concurrency so a newer push cancels an older build that has not started deployment.

## Testing

Automated tests cover:

- Ed25519 license generation and validation.
- Rejection of a wrong public key, modified payload, wrong fingerprint, unsupported version, and expired license.
- Management command behavior when the private key path is absent or invalid.
- Artifact allowlist parsing and exclusion rules.
- Artifact verification failing when protected source, secrets, or Git metadata are present.
- Artifact verification succeeding when every allowlisted module has a compiled extension and no protected source.
- Django system checks and focused application tests before artifact upload.

Deployment verification confirms the systemd service is active after restart and performs an HTTP request against `http://127.0.0.1:8000/`; any HTTP response below 500 is accepted because the root route may redirect unauthenticated users. Rollback is treated as a deployment failure and leaves the GitHub job red even when the previous release is restored successfully.

## Rollout Sequence

1. Add Ed25519 support, tests, key-generation tooling, and documentation.
2. Generate the owner keypair locally, commit only the public key, and issue the 2026 license.
3. Add and test the Cython artifact builder locally where possible and in GitHub-hosted Linux CI.
4. Add the build-and-deploy workflow while retaining the current deployment as a manual fallback.
5. Create the production venv and update the systemd paths once.
6. Deploy the first protected artifact, verify application workflows, license enforcement, logs, and rollback metadata.
7. Stop using the source checkout. Remove it only after owner approval and a confirmed protected release.

## Success Criteria

- AlmaLinux starts only with a valid version 2 license for its machine ID and expiration date.
- The server contains no private signing material or shared signing secret.
- Protected modules are present in the active release only as CPython extension binaries, not `.py` source.
- Normal pushes build and deploy an artifact without `git pull` on AlmaLinux.
- Failed releases automatically restore the previous working release.
- Existing Django tests and production health checks pass before a release is accepted.
