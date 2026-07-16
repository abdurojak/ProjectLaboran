# Production Code Protection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the shared-secret license with Ed25519 signatures and deploy Cython-compiled production artifacts to AlmaLinux without pulling protected source code onto the server.

**Architecture:** The owner laptop creates an Ed25519 keypair and signs machine-bound licenses; the application embeds only the public key. A GitHub-hosted manylinux job compiles an allowlist of sensitive modules, verifies that their source and all secrets are absent, and uploads an artifact. The self-hosted AlmaLinux job installs a versioned release and switches an atomic `current` symlink with rollback on failed health checks.

**Tech Stack:** Django 4.2, Python `cryptography` Ed25519, Cython 3, GitHub Actions, manylinux_2_28, systemd, Daphne

---

## File Map

- Modify `requirements.txt`: add the runtime `cryptography` dependency.
- Create `requirements-build.txt`: isolate Cython as a build-only dependency.
- Modify `.gitignore`: ignore owner private keys, local artifact staging, and generated archives.
- Modify `apps/core/licensing.py`: version 2 Ed25519 license encoding and validation.
- Create `apps/core/license_public_key.py`: generated public verification key embedded in production.
- Create `apps/core/management/commands/generate_labhub_license_keypair.py`: generate the owner keypair and public-key module.
- Modify `apps/core/management/commands/generate_labhub_license.py`: sign with the owner private key file.
- Modify `apps/core/test_licensing.py`: cover Ed25519 behavior and commands.
- Create `deployment/protected_modules.txt`: authoritative Cython allowlist.
- Create `deployment/artifact.py`: artifact path rules and verification logic.
- Create `deployment/build_protected_artifact.py`: copy, compile, strip, verify, and archive a release.
- Create `deployment/verify_protected_artifact.py`: standalone CI verification command.
- Create `deployment/deploy_release.sh`: locked versioned deployment and rollback.
- Create `deployment/tests/test_artifact.py`: artifact security tests.
- Modify `.github/workflows/test-runner.yml`: GitHub-hosted build plus self-hosted artifact deployment.
- Modify `.env.example`: remove shared verification secret and document version 2 settings.
- Modify `docs/LICENSE_DEPLOYMENT.md`: key custody, build ABI, rollout, rollback, and server commands.

## Task 1: Freeze Automatic Production Deployment During Migration

**Files:**
- Modify: `.github/workflows/test-runner.yml`

- [ ] **Step 1: Change the workflow trigger to manual-only**

Keep the existing deploy job unchanged and replace the trigger with:

```yaml
on:
  workflow_dispatch:
```

This commit must be pushed before any license implementation commit. GitHub reads the workflow from the pushed commit, so this safety-gate push does not deploy; later implementation pushes also remain manual until production is ready.

- [ ] **Step 2: Validate the workflow diff**

Run:

```powershell
git diff --check
git diff -- .github/workflows/test-runner.yml
```

Expected: only the `push` trigger is removed; the existing deployment commands are unchanged.

- [ ] **Step 3: Commit and push the safety gate**

```powershell
git add .github/workflows/test-runner.yml
git commit -m "ci: pause automatic deploy during license migration"
git pull --rebase origin main
git push origin main
```

Expected: GitHub accepts the push and no deployment starts automatically.

## Task 2: Replace HMAC Licensing With Ed25519

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Create: `apps/core/license_public_key.py`
- Modify: `apps/core/licensing.py`
- Modify: `apps/core/test_licensing.py`

- [ ] **Step 1: Add failing Ed25519 license tests**

Replace HMAC fixtures in `apps/core/test_licensing.py` with an in-memory keypair and add explicit version and tamper tests:

```python
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def make_keypair():
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode('ascii')
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode('ascii')
    return private_pem, public_pem
```

Tests must assert:

```python
claims = validate_license_key(
    build_license_key('Lab FTI', 'server-utama', date(2026, 12, 31), private_pem),
    fingerprint='server-utama',
    public_key_pem=public_pem,
    today=date(2026, 7, 16),
)
self.assertEqual(claims['version'], 2)
```

Add separate tests that reject a different public key, a payload with one changed character, `version: 1`, a mismatched fingerprint, and an expired date.

- [ ] **Step 2: Install the test dependency and verify RED**

First add exactly this runtime pin to `requirements.txt`:

```text
cryptography==45.0.5
```

Install and run:

```powershell
.\.venv\Scripts\python.exe -m pip install cryptography==45.0.5
.\.venv\Scripts\python.exe manage.py test apps.core.test_licensing --settings=project_laboran.test_settings
```

Expected: tests fail because the current API expects `verification_secret` and signs with HMAC.

- [ ] **Step 3: Implement minimal Ed25519 signing and validation**

In `apps/core/licensing.py`, remove `hashlib` and `hmac`, import Ed25519 primitives, add `version: 2` to canonical claims, and implement:

```python
def build_license_key(customer, fingerprint, expires_on, private_key_pem):
    claims = {
        'customer': customer,
        'expires_on': expires_on.isoformat(),
        'fingerprint': fingerprint,
        'version': 2,
    }
    payload = _b64encode(_json_dumps(claims))
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode('ascii'),
        password=None,
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise LicenseError('License private key must be Ed25519.')
    return f'{payload}.{_b64encode(private_key.sign(payload.encode("ascii")))}'


def validate_license_key(license_key, fingerprint, public_key_pem, today=None):
    payload, signature = _split_license_key(license_key)
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode('ascii'))
        if not isinstance(public_key, Ed25519PublicKey):
            raise LicenseError('License public key must be Ed25519.')
        public_key.verify(_b64decode(signature), payload.encode('ascii'))
    except (ValueError, InvalidSignature) as exc:
        raise LicenseError('License signature is invalid.') from exc

    claims = _load_claims(payload)
    if claims.get('version') != 2:
        raise LicenseError('License version is unsupported.')
    if claims.get('fingerprint') != fingerprint:
        raise LicenseError('License fingerprint does not match this server.')
    expires_on = date.fromisoformat(claims['expires_on'])
    if (today or date.today()) > expires_on:
        raise LicenseError('License has expired.')
    return claims
```

`enforce_configured_license()` imports `PUBLIC_KEY_PEM` from `apps.core.license_public_key` and passes it to validation. Create `license_public_key.py` with `PUBLIC_KEY_PEM = ''` until Task 4 generates the real owner key.

- [ ] **Step 4: Run focused tests to verify GREEN**

```powershell
.\.venv\Scripts\python.exe manage.py test apps.core.test_licensing --settings=project_laboran.test_settings
```

Expected: all Ed25519 unit and startup tests pass.

- [ ] **Step 5: Protect owner key filenames**

Append to `.gitignore`:

```gitignore
.secrets/
*.ed25519.pem
build/protected/
dist/protected/
*.protected.tar.gz
```

- [ ] **Step 6: Commit the license core**

```powershell
git add requirements.txt .gitignore apps/core/licensing.py apps/core/license_public_key.py apps/core/test_licensing.py
git commit -m "feat: verify licenses with Ed25519"
```

Do not push yet.

## Task 3: Add Owner Key And License Commands

**Files:**
- Create: `apps/core/management/commands/generate_labhub_license_keypair.py`
- Modify: `apps/core/management/commands/generate_labhub_license.py`
- Modify: `apps/core/test_licensing.py`

- [ ] **Step 1: Add failing command tests**

Use `TemporaryDirectory` and assert that the keypair command:

```python
call_command(
    'generate_labhub_license_keypair',
    '--private-key-file', str(private_path),
    '--public-key-module', str(public_module_path),
)
self.assertTrue(private_path.read_text().startswith('-----BEGIN PRIVATE KEY-----'))
self.assertIn('PUBLIC_KEY_PEM', public_module_path.read_text())
```

Update the license command test to set:

```python
with patch.dict('os.environ', {'LABHUB_LICENSE_PRIVATE_KEY_FILE': str(private_path)}):
    call_command('generate_labhub_license', ...)
```

Add tests that reject a missing private key file and refuse to overwrite an existing private key unless `--force` is supplied.

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe manage.py test apps.core.test_licensing --settings=project_laboran.test_settings
```

Expected: unknown `generate_labhub_license_keypair` command and old signing-secret behavior.

- [ ] **Step 3: Implement the keypair command**

Generate an Ed25519 key, write unencrypted PKCS8 PEM to the requested private path, and serialize the public module without manual substitution:

```python
public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode('ascii')
public_module_path.write_text(
    f'PUBLIC_KEY_PEM = {public_pem!r}\n',
    encoding='ascii',
)
```

The command creates parent directories, uses exclusive creation unless `--force`, and calls `os.chmod(private_path, 0o600)` where supported. The module output is deterministic for the generated key and contains no private material.

- [ ] **Step 4: Update the license command**

Read `LABHUB_LICENSE_PRIVATE_KEY_FILE`, load its text, validate `--expires-on` with `date.fromisoformat`, and call `build_license_key(..., private_key_pem=private_pem)`. Remove every reference to `LABHUB_LICENSE_SIGNING_SECRET`.

- [ ] **Step 5: Verify GREEN and commit**

```powershell
.\.venv\Scripts\python.exe manage.py test apps.core.test_licensing --settings=project_laboran.test_settings
git add apps/core/management/commands apps/core/test_licensing.py
git commit -m "feat: add Ed25519 license owner tooling"
```

## Task 4: Generate The Owner Keypair And 2026 Server License

**Files:**
- Modify: `apps/core/license_public_key.py`
- Create locally but ignore: `.secrets/labhub-license-private.ed25519.pem`

- [ ] **Step 1: Generate the real owner keypair**

```powershell
.\.venv\Scripts\python.exe manage.py generate_labhub_license_keypair --private-key-file .secrets/labhub-license-private.ed25519.pem --public-key-module apps/core/license_public_key.py
```

Expected: private PEM exists under ignored `.secrets`; the public module contains only `BEGIN PUBLIC KEY`.

- [ ] **Step 2: Prove the private key is ignored and absent from staged data**

```powershell
git check-ignore .secrets/labhub-license-private.ed25519.pem
git grep -n "BEGIN PRIVATE KEY" -- . ':!.secrets'
```

Expected: `git check-ignore` prints the private path; `git grep` prints nothing.

- [ ] **Step 3: Generate the replacement server license**

```powershell
$env:LABHUB_LICENSE_PRIVATE_KEY_FILE=(Resolve-Path .secrets/labhub-license-private.ed25519.pem)
.\.venv\Scripts\python.exe manage.py generate_labhub_license --customer "ProjectLaboran Production" --fingerprint "4f6341d9347846bfb5935068e67c546e" --expires-on 2026-12-31
```

Store the printed license in the handoff notes, not in any tracked file.

- [ ] **Step 4: Commit only the public key**

```powershell
git add apps/core/license_public_key.py
git commit -m "chore: embed production license public key"
```

## Task 5: Build And Verify Protected Artifacts

**Files:**
- Create: `requirements-build.txt`
- Create: `deployment/__init__.py`
- Create: `deployment/protected_modules.txt`
- Create: `deployment/artifact.py`
- Create: `deployment/build_protected_artifact.py`
- Create: `deployment/verify_protected_artifact.py`
- Create: `deployment/tests/__init__.py`
- Create: `deployment/tests/test_artifact.py`

- [ ] **Step 1: Add the build dependency and allowlist**

`requirements-build.txt`:

```text
-r requirements.txt
Cython==3.1.2
setuptools==80.9.0
wheel==0.45.1
```

`deployment/protected_modules.txt`:

```text
apps/core/licensing.py
apps/core/license_public_key.py
apps/mobile_api/jwt_service.py
apps/asleb/services.py
apps/peminjaman/services.py
apps/pendaftaran_asleb/services.py
apps/barang_tertinggal/services.py
```

- [ ] **Step 2: Write failing artifact-rule tests**

Tests use temporary directories and real files. Cover normalized allowlist parsing, forbidden `.env`/`.git`/private PEM detection, protected-source detection, missing extension detection, and a successful tree containing `licensing.cpython-311-x86_64-linux-gnu.so` without `licensing.py`.

The desired API is:

```python
protected = load_protected_modules(allowlist_path)
errors = inspect_release_tree(release_root, protected)
self.assertEqual(errors, [])
```

- [ ] **Step 3: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest deployment.tests.test_artifact -v
```

Expected: import failure for `deployment.artifact`.

- [ ] **Step 4: Implement artifact inspection**

`load_protected_modules()` returns normalized `PurePosixPath` entries and rejects absolute paths or `..`. `inspect_release_tree()` recursively rejects:

```python
FORBIDDEN_NAMES = {'.env', '.env.backup', '.git', '.secrets'}
FORBIDDEN_SUFFIXES = {'.pem'}
```

For every allowlisted `.py`, it rejects the source path and requires at least one sibling extension matching `<stem>.*.so` or `<stem>.pyd`.

- [ ] **Step 5: Verify GREEN**

```powershell
.\.venv\Scripts\python.exe -m unittest deployment.tests.test_artifact -v
```

Expected: all artifact security tests pass.

- [ ] **Step 6: Implement the build command**

The builder accepts `--source`, `--staging`, `--output`, and `--allowlist`. It copies with `shutil.copytree` while excluding `.git`, `.venv`, `venv`, `.secrets`, `media`, `staticfiles`, test modules, caches, and prior build output. It compiles every allowlisted module using `setuptools.Extension` plus `cythonize(language_level=3)`, copies extensions in place, deletes generated `.c` files and protected `.py` files, runs `inspect_release_tree`, and writes a `tar.gz` with the release at archive root.

- [ ] **Step 7: Implement standalone verification**

The verifier accepts a directory or `tar.gz`, extracts archives to a temporary directory, calls `inspect_release_tree`, prints each error, and exits nonzero on any error.

- [ ] **Step 8: Build locally and commit**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe deployment/build_protected_artifact.py --source . --staging build/protected/release --output dist/protected/projectlaboran.protected.tar.gz --allowlist deployment/protected_modules.txt
.\.venv\Scripts\python.exe deployment/verify_protected_artifact.py dist/protected/projectlaboran.protected.tar.gz --allowlist deployment/protected_modules.txt
git add requirements-build.txt deployment
git commit -m "feat: build verified Cython production artifacts"
```

Expected: the Windows build verifies structural rules. Linux importability is verified in Task 7.

## Task 6: Add Versioned Deploy And Rollback Script

**Files:**
- Create: `deployment/deploy_release.sh`
- Modify: `docs/LICENSE_DEPLOYMENT.md`

- [ ] **Step 1: Implement fail-fast deployment**

The script uses `set -Eeuo pipefail`, `flock`, and these fixed paths:

```bash
BASE_DIR=/home/admin/LabTif
RELEASES_DIR="$BASE_DIR/releases"
CURRENT_LINK="$BASE_DIR/current"
VENV_DIR="$BASE_DIR/production-venv"
SERVICE=projectlaboran-daphne
```

It accepts one archive path, records `readlink -f "$CURRENT_LINK"` when present, extracts into `releases/$GITHUB_SHA`, creates the venv when absent, installs `requirements.txt`, runs migrations and static collection from the new release, switches `current` with `ln -sfn`, restarts Daphne, verifies `systemctl is-active`, and probes `/` with curl while accepting status `<500`.

An `ERR` trap restores the prior symlink and restarts Daphne when failure occurs after switching. It retains the active release plus the two newest inactive releases.

- [ ] **Step 2: Validate shell syntax**

Run in Git Bash or CI:

```bash
bash -n deployment/deploy_release.sh
```

Expected: exit 0 and no output.

- [ ] **Step 3: Document one-time server changes**

Update `docs/LICENSE_DEPLOYMENT.md` with exact commands to create `/home/admin/LabTif/releases`, `/home/admin/LabTif/production-venv`, update the systemd `WorkingDirectory` and `ExecStart`, replace the old environment with the version 2 key, and verify `python` ABI.

- [ ] **Step 4: Commit**

```powershell
git add deployment/deploy_release.sh docs/LICENSE_DEPLOYMENT.md
git commit -m "feat: deploy protected releases with rollback"
```

## Task 7: Replace Source Pull Workflow With Artifact Deployment

**Files:**
- Modify: `.github/workflows/test-runner.yml`

- [ ] **Step 1: Define workflow safety and ABI**

Keep rollout manual-only and add:

```yaml
name: Build and Deploy Protected AlmaLinux

on:
  workflow_dispatch:

concurrency:
  group: projectlaboran-production
  cancel-in-progress: false

env:
  PYTHON_ABI: ${{ vars.DEPLOY_PYTHON_ABI || 'cp311-cp311' }}
```

- [ ] **Step 2: Add the GitHub-hosted build job**

Use `ubuntu-latest` with container `quay.io/pypa/manylinux_2_28_x86_64`, checkout source, select `/opt/python/${PYTHON_ABI}/bin/python`, install `requirements-build.txt`, run the full Django tests with test settings, build and verify the artifact, run `manage.py check` from the staged tree with `LABHUB_LICENSE_ENFORCED=False`, and upload `projectlaboran.protected.tar.gz` with `actions/upload-artifact`.

Upload both the archive and deployment script in one artifact:

```yaml
- uses: actions/upload-artifact@v4
  with:
    name: projectlaboran-protected
    path: |
      dist/protected/projectlaboran.protected.tar.gz
      deployment/deploy_release.sh
```

- [ ] **Step 3: Add the self-hosted deploy job**

Use:

```yaml
deploy:
  needs: build
  runs-on: [self-hosted, linux, x64]
  steps:
    - uses: actions/download-artifact@v4
      with:
        name: projectlaboran-protected
        path: /home/admin/LabTif/incoming
    - name: Deploy protected release
      run: bash /home/admin/LabTif/incoming/deploy_release.sh /home/admin/LabTif/incoming/projectlaboran.protected.tar.gz
```

The deploy job must not use `actions/checkout` and must contain no `git pull`.

- [ ] **Step 4: Verify workflow invariants and commit**

```powershell
rg -n "git pull|actions/checkout" .github/workflows/test-runner.yml
git diff --check
git add .github/workflows/test-runner.yml
git commit -m "ci: deploy protected artifacts to AlmaLinux"
```

Expected: `actions/checkout` appears only in the build job; `git pull` appears nowhere.

## Task 8: Update Configuration And Run Full Verification

**Files:**
- Modify: `.env.example`
- Modify: `docs/LICENSE_DEPLOYMENT.md`

- [ ] **Step 1: Remove shared-secret configuration**

Delete `LABHUB_LICENSE_VERIFICATION_SECRET` from `.env.example`. Keep:

```env
LABHUB_LICENSE_ENFORCED=False
LABHUB_LICENSE_KEY=
LABHUB_LICENSE_FINGERPRINT=
```

Document `LABHUB_LICENSE_PRIVATE_KEY_FILE` only under owner-side generation instructions, never as a server variable.

- [ ] **Step 2: Run all verification commands fresh**

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=project_laboran.test_settings
.\.venv\Scripts\python.exe manage.py check --settings=project_laboran.test_settings
.\.venv\Scripts\python.exe -m unittest deployment.tests.test_artifact -v
.\.venv\Scripts\python.exe deployment/build_protected_artifact.py --source . --staging build/protected/release --output dist/protected/projectlaboran.protected.tar.gz --allowlist deployment/protected_modules.txt
.\.venv\Scripts\python.exe deployment/verify_protected_artifact.py dist/protected/projectlaboran.protected.tar.gz --allowlist deployment/protected_modules.txt
git diff --check
git status --short
```

Expected: all tests/checks exit 0; artifact verification reports no protected source or secret; only intentional tracked changes and ignored local secrets remain.

- [ ] **Step 3: Commit documentation and environment changes**

```powershell
git add .env.example docs/LICENSE_DEPLOYMENT.md
git commit -m "docs: document protected artifact rollout"
```

## Task 9: Coordinated Production Rollout

**Files:**
- No repository changes until protected deployment succeeds.

- [ ] **Step 1: Push implementation while deployment remains manual**

```powershell
git pull --rebase origin main
git push origin main
```

Expected: code reaches GitHub but no production deployment starts because the workflow is `workflow_dispatch` only.

- [ ] **Step 2: Confirm the server ABI**

On AlmaLinux:

```bash
/home/admin/LabTif/ProjectLaboran/venv/bin/python -c "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}')"
```

Set the exact output as repository variable `DEPLOY_PYTHON_ABI` under GitHub Settings > Secrets and variables > Actions > Variables.

- [ ] **Step 3: Install the version 2 license and systemd paths**

Update `/etc/systemd/system/projectlaboran-daphne.service` to use `/home/admin/LabTif/current` and `/home/admin/LabTif/production-venv`, replace `LABHUB_LICENSE_KEY` with the Task 4 output, and remove `LABHUB_LICENSE_VERIFICATION_SECRET`. Run `sudo systemctl daemon-reload` but do not restart before the first artifact has created `current`.

- [ ] **Step 4: Run the protected deployment manually**

In GitHub Actions, run `Build and Deploy Protected AlmaLinux`. Confirm both jobs are green, then verify:

```bash
sudo systemctl status projectlaboran-daphne --no-pager
readlink -f /home/admin/LabTif/current
find /home/admin/LabTif/current/apps/core -maxdepth 1 -name 'licensing*' -print
curl -I http://127.0.0.1:8000/
```

Expected: service is active; `current` points to a release; `licensing` is a `.so` and `licensing.py` is absent; HTTP status is below 500.

- [ ] **Step 5: Restore push-triggered deployment after confirmation**

Add back:

```yaml
  push:
    branches:
      - main
```

Run `git diff --check`, commit as `ci: enable protected automatic deployment`, and push. Future pushes now build and deploy artifacts.

- [ ] **Step 6: Preserve the old checkout until explicit owner approval**

Do not delete `/home/admin/LabTif/ProjectLaboran` as part of automation. Once the owner verifies all workflows and backups, provide a separate, explicit cleanup procedure. The old checkout already contains historical source and deleting it cannot invalidate copies made earlier.
