# LabHub Protected Deployment

Deployment production memakai root-owned launcher, GitHub-hosted artifact provenance,
release immutable, dedicated runtime user, dan transaction journal untuk code serta
environment. Self-hosted runner hanya boleh menaruh satu envelope pada direktori
incoming dan meminta launcher terpasang untuk memprosesnya.

## License v2 di laptop owner

Private key Ed25519 hanya berada di laptop owner. Jangan unggah ke Git, Actions,
artifact, runner, atau server. Ambil fingerprint server dengan `cat /etc/machine-id`,
lalu generate license menggunakan file private key:

```bash
export LABHUB_LICENSE_PRIVATE_KEY_FILE="$HOME/.secrets/labhub-license-private.ed25519.pem"
python manage.py generate_labhub_license --customer "Lab FTI" --fingerprint "<machine-id-server>" --expires-on 2030-01-31
```

Output menjadi `LABHUB_LICENSE_KEY` v2. Server tidak menyimpan private key, signing
secret, atau verification secret v2.

## Trust artifact GitHub

GitHub menjelaskan bahwa artifact attestation mengikat artifact ke repository,
commit, dan workflow pembuatnya; public repository memakai Sigstore Public Good
Instance. Verifikasi lokal memerlukan GitHub CLI, artifact, bundle, serta trusted
root. Lihat dokumentasi resmi [artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations),
[offline verification](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/verify-attestations-offline),
dan [`gh attestation verify`](https://cli.github.com/manual/gh_attestation_verify).

Attestation membuktikan provenance, bukan freshness. Karena repository public,
launcher root juga mengambil
`https://api.github.com/repos/abdurojak/ProjectLaboran/commits/main` melalui HTTPS
terverifikasi (`--disable`, `--noproxy '*'`, `--proto '=https'`, TLS minimum 1.2),
parse JSON tanpa `eval`, dan
mewajibkan `source-sha` sama persis dengan HEAD `main`. Network, DNS, TLS, API,
format JSON, dan rate-limit error semuanya fail closed. Check dilakukan setelah
attestation, setelah build sebelum publication, dan tepat sebelum activation setelah
management command. Masih ada race kecil bila `main` bergerak tepat setelah check
terakhir; bila `main` berubah selama build/deploy, hasilkan ulang dan deploy build
HEAD terbaru.

Install GitHub CLI dari repository package resmi GitHub CLI untuk AlmaLinux, lalu
pastikan executable root-installed tersedia pada path yang dipakai launcher:

```bash
test "$(command -v gh)" = /usr/bin/gh
test "$(command -v curl)" = /usr/bin/curl
sudo test "$(stat -c '%U:%G' /usr/bin/gh)" = root:root
/usr/bin/gh version
/usr/bin/curl --version
```

Ambil trusted root dengan GitHub CLI dan install sebagai file immutable bagi runner:

```bash
sudo install -d -o root -g root -m 0700 /etc/labhub
TRUST_TMP=$(sudo mktemp /etc/labhub/.trusted-root.XXXXXX)
sudo /usr/bin/gh attestation trusted-root | sudo tee "$TRUST_TMP" >/dev/null
sudo chown root:root "$TRUST_TMP"
sudo chmod 0644 "$TRUST_TMP"
sudo mv -Tf "$TRUST_TMP" /etc/labhub/trusted_root.jsonl
sudo test "$(stat -c '%U:%G %a' /etc/labhub/trusted_root.jsonl)" = 'root:root 644'
```

Perbarui trusted root saat owner mengimpor artifact baru, sesuai panduan GitHub.
Task 7 membuat dan mengunduh bundle attestation lalu membungkus tiga file berikut
tepat di root tar envelope:

```text
projectlaboran.protected.tar.gz
attestation.jsonl
source-sha
```

Envelope adalah tar **tanpa kompresi** dengan tepat tiga regular file mode `0644`,
tanpa directory entry tambahan. `source-sha` berisi tepat 40 lowercase hex plus
optional final newline.

`projectlaboran.protected.tar.gz` yang ter-attest wajib memuat `requirements.lock`
dan `wheelhouse/` selain source aplikasi. Keduanya berada di dalam protected archive,
bukan sebagai file envelope tambahan:

```text
manage.py
requirements.lock
wheelhouse/<distribution-wheels>.whl
...
```

Task 7 menjalankan interpreter manylinux dengan ABI yang sama, meng-install versi
`pip-tools` yang dipin di workflow, menghasilkan fully resolved
`requirements.lock` memakai `pip-compile --generate-hashes`, lalu menjalankan
`pip download --only-binary=:all: --require-hashes -r requirements.lock` untuk
mengunduh tepat dependency wheels ke `wheelhouse/` sebelum protected archive dan
attestation final dibuat. Launcher tidak mengakses index package dan hanya menjalankan:

```bash
python -m pip install --no-index --find-links /root-owned/candidate/wheelhouse --require-hashes -r /root-owned/candidate/requirements.lock
```

Path di atas menjelaskan bentuk command; launcher menggantinya dengan path candidate
root-owned aktual. Missing lock, wheel non-regular, link/device, sdist, hash mismatch,
atau dependency yang tidak lengkap menggagalkan deployment. Lock yang mencoba URL,
direct reference, editable/local path, index/find-links override, atau ekspansi env
juga ditolak; `PIP_CONFIG_FILE=/dev/null` dan `PIP_NO_INDEX=1` memastikan install
candidate tidak melakukan akses network.

Launcher mengeksekusi policy berikut dan menyembunyikan detail output attestation
dari deployment log:

```bash
gh attestation verify projectlaboran.protected.tar.gz \
  --repo abdurojak/ProjectLaboran \
  --bundle attestation.jsonl \
  --custom-trusted-root /etc/labhub/trusted_root.jsonl \
  --signer-workflow abdurojak/ProjectLaboran/.github/workflows/test-runner.yml \
  --source-digest '<40-lowercase-hex-source-sha>' \
  --source-ref refs/heads/main \
  --deny-self-hosted-runners
```

Build provenance GitHub-hosted adalah trust anchor. Output job self-hosted tidak
dipercaya dan `--deny-self-hosted-runners` wajib tetap aktif. Root launcher merekam
digest snapshot envelope, digest protected archive, dan SHA sebagai record
`consumed`/`deployed` append-only pada `/home/admin/LabTif/.deploy-history`. Replay
envelope atau archive yang pernah consumed ditolak; downgrade hanya boleh melalui
rollback manual owner.

## Dedicated runtime dan build user

Buat dua system user locked tanpa login. `labhub-build` hanya membuat venv dan
memasang wheel offline di candidate private; `labhub-app` hanya menjalankan code yang
sudah sealed. `admin` tetap menjalankan runner tetapi tidak memakai salah satu UID:

```bash
getent group labhub-app >/dev/null || sudo groupadd --system labhub-app
id labhub-app >/dev/null 2>&1 || sudo useradd --system --gid labhub-app --home-dir /var/lib/labhub-app --create-home --shell /sbin/nologin labhub-app
getent group labhub-build >/dev/null || sudo groupadd --system labhub-build
id labhub-build >/dev/null 2>&1 || sudo useradd --system --gid labhub-build --home-dir /var/lib/labhub-build --create-home --shell /sbin/nologin labhub-build
sudo passwd -l labhub-app
sudo passwd -l labhub-build
sudo chown root:root /var/lib/labhub-app
sudo chown root:root /var/lib/labhub-build
sudo chmod 0755 /var/lib/labhub-app
sudo chmod 0755 /var/lib/labhub-build
test "$(id -gn labhub-app)" = labhub-app
test "$(id -gn labhub-build)" = labhub-build
test "$(id -u labhub-app)" != "$(id -u labhub-build)"
! id -nG admin | tr ' ' '\n' | grep -Fx labhub-build
! id -nG labhub-app | tr ' ' '\n' | grep -Fx labhub-build
```

Ownership base baru diubah setelah media cutover dan validasi checkout lama selesai.

## Dual environment v1 dan v2

Jangan mengganti nilai environment v1 sebelum protected deployment pertama. Buat
directory root-only dan salin nilai dari unit production yang sedang bekerja ke
`labhub-v1.env` melalui `sudoedit`; termasuk license v1 dan verification secret lama
untuk sementara. Jangan menampilkan nilainya melalui `systemctl show` atau log:

```bash
sudo install -d -o root -g root -m 0700 /etc/labhub
sudo install -o root -g root -m 0600 /dev/null /etc/labhub/labhub-v1.env
sudoedit /etc/labhub/labhub-v1.env
sudo chown root:root /etc/labhub/labhub-v1.env
sudo chmod 0600 /etc/labhub/labhub-v1.env
```

Format file sengaja ketat: satu `NAME=value` per baris, tanpa shell quotes,
substitution, whitespace, backslash, `#`, atau multiline value. Nilai menerima
alphanumeric serta punctuation URL umum. Regenerate secret ke format ini bila perlu.
Contoh struktur v1, bukan nilai production:

```env
SECRET_KEY=<existing-url-safe-production-secret>
DEBUG=False
ALLOWED_HOSTS=<production-hosts>
DB_NAME=<database-name>
DB_USER=<database-user>
DB_PASSWORD=<url-safe-database-password>
DB_HOST=<database-host>
DB_PORT=3306
MEDIA_ROOT=/var/lib/labhub/media
LABHUB_LICENSE_ENFORCED=True
LABHUB_LICENSE_KEY=<existing-v1-license>
LABHUB_LICENSE_VERIFICATION_SECRET=<existing-v1-secret-temporarily>
```

Buat v2 secara terpisah dengan seluruh runtime secret yang sama tetapi license v2
baru dan tanpa verification/private/signing secret:

```bash
sudo install -o root -g root -m 0600 /dev/null /etc/labhub/labhub-v2.env
sudoedit /etc/labhub/labhub-v2.env
sudo chown root:root /etc/labhub/labhub-v2.env
sudo chmod 0600 /etc/labhub/labhub-v2.env
```

```env
SECRET_KEY=<existing-url-safe-production-secret>
DEBUG=False
ALLOWED_HOSTS=<production-hosts>
DB_NAME=<database-name>
DB_USER=<database-user>
DB_PASSWORD=<url-safe-database-password>
DB_HOST=<database-host>
DB_PORT=3306
MEDIA_ROOT=/var/lib/labhub/media
LABHUB_LICENSE_ENFORCED=True
LABHUB_LICENSE_KEY=<license-v2-from-owner-laptop>
```

Tambahkan juga runtime variable existing untuk API, email, Redis, dan integrasi lain.
`LABHUB_LICENSE_FINGERPRINT` boleh ada bila license owner memang memakai override;
v2 tetap tidak boleh memuat verification, signing, atau private-key variable.

Set stable environment link ke v1 sebelum rollout:

```bash
sudo ln -s /etc/labhub/labhub-v1.env /etc/labhub/.current.env.bootstrap
sudo mv -Tf /etc/labhub/.current.env.bootstrap /etc/labhub/current.env
sudo chown -h root:root /etc/labhub/current.env
sudo test "$(readlink -f /etc/labhub/current.env)" = /etc/labhub/labhub-v1.env
sudo test "$(stat -c '%U:%G %a' /etc/labhub/labhub-v1.env)" = 'root:root 600'
sudo test "$(stat -c '%U:%G %a' /etc/labhub/labhub-v2.env)" = 'root:root 600'
```

Runner tidak mendapat file atau nilai environment production.

## Persistent media dan akses UID

Artifact tidak pernah berisi uploaded media. Parent `/var/lib/labhub` sengaja
dimiliki UID `admin`, sehingga proses Daphne admin yang sudah berjalan langsung dapat
traverse/write tanpa menunggu supplementary group baru. ACL memberi akses masa depan
kepada `labhub-app` dan read-only kepada Nginx:

```bash
sudo dnf install -y acl policycoreutils-python-utils rsync
getent group labhub-media >/dev/null || sudo groupadd --system labhub-media
sudo usermod -aG labhub-media labhub-app
sudo usermod -aG labhub-media nginx
sudo install -d -o admin -g labhub-media -m 2750 /var/lib/labhub
sudo install -d -o admin -g labhub-media -m 2750 /var/lib/labhub/media
sudo setfacl -m u:admin:rwx,u:labhub-app:rwx,u:nginx:rx,g::rx,m::rwx,o::--- /var/lib/labhub /var/lib/labhub/media
sudo setfacl -d -m u:admin:rwx,u:labhub-app:rwx,u:nginx:rx,g::rx,m::rwx,o::--- /var/lib/labhub/media
sudo rsync -a --chown=admin:labhub-media --chmod=D2750,F640 -- /home/admin/LabTif/ProjectLaboran/media/ /var/lib/labhub/media/
sudo setfacl -Rm u:admin:rwX,u:labhub-app:rwX,u:nginx:rX,m::rwX /var/lib/labhub/media
sudo -u admin test -w /var/lib/labhub/media
sudo -u labhub-app test -w /var/lib/labhub/media
sudo -u nginx test -r /var/lib/labhub/media
```

## Nginx, SELinux, dan maintenance

Django/Daphne dengan `DEBUG=False` tidak melayani static **atau** media production.
Di dalam server block production, gunakan static dari release aktif, alias media
persistent, dan root-owned maintenance include:

```nginx
include /etc/nginx/labhub-maintenance.conf;

location /static/ {
    alias /home/admin/LabTif/current/staticfiles/;
    autoindex off;
    add_header X-Content-Type-Options nosniff always;
}

location /media/ {
    alias /var/lib/labhub/media/;
    autoindex off;
    add_header X-Content-Type-Options nosniff always;
}
```

```bash
sudo test -e /etc/nginx/labhub-maintenance.conf || sudo install -o root -g root -m 0644 /dev/null /etc/nginx/labhub-maintenance.conf
sudo semanage fcontext -a -t httpd_sys_content_t '/var/lib/labhub/media(/.*)?'
sudo semanage fcontext -a -t httpd_sys_content_t '/home/admin/LabTif/releases/[0-9a-f]{40}/staticfiles(/.*)?'
sudo setsebool -P httpd_enable_homedirs 1
sudo restorecon -Rv /var/lib/labhub/media
if sudo test -d /home/admin/LabTif/releases; then
    sudo restorecon -RFv /home/admin/LabTif/releases
fi
sudo nginx -t
sudo systemctl reload nginx
```

Rule fcontext static bersifat persistent untuk semua release SHA. Launcher menjalankan
`restorecon` pada static tree setelah candidate sealed dipublish ke path final. Boolean
home-directory hanya memberi izin SELinux; DAC tetap membatasi Nginx ke traversal
`/home/admin` dan read-only static tree yang root-owned. Audit home lain agar tidak
world-readable.

Port 8000 tidak boleh externally reachable. Hapus exposure firewalld dan verifikasi
dari host lain bahwa koneksi ke `<server-private-address>:8000` gagal:

```bash
if sudo firewall-cmd --query-port=8000/tcp; then sudo firewall-cmd --remove-port=8000/tcp; fi
if sudo firewall-cmd --permanent --query-port=8000/tcp; then sudo firewall-cmd --permanent --remove-port=8000/tcp; fi
sudo firewall-cmd --reload
if sudo firewall-cmd --query-port=8000/tcp; then exit 1; fi
curl --fail --max-time 5 http://127.0.0.1:8000/ >/dev/null
```

## Media cutover tanpa restart Daphne

Tetap jalankan checkout lama sebagai proses admin. Blok traffic/write di Nginx tanpa
stop/restart Daphne:

```bash
printf 'return 503;\n' | sudo tee /etc/nginx/labhub-maintenance.conf >/dev/null
sudo nginx -t
sudo systemctl reload nginx
status=$(curl --silent --output /dev/null --write-out '%{http_code}' -H 'Host: <production-hostname>' http://127.0.0.1/)
test "$status" = 503
```

Final-sync, pastikan tidak ada delta, lalu preserve direktori lama dan publish symlink.
Trap menutup gap jika signal/error terjadi setelah rename pertama:

```bash
(
    set -Eeuo pipefail
    OLD_MEDIA=/home/admin/LabTif/ProjectLaboran/media
    MEDIA_BACKUP=/home/admin/LabTif/ProjectLaboran/media.pre-persistent
    TEMP_LINK=/home/admin/LabTif/ProjectLaboran/.media.persistent.$$
    MOVED=false

    restore_old_media() {
        status=${1:-$?}
        trap - ERR INT TERM HUP
        set +e
        test ! -L "$TEMP_LINK" || rm -f -- "$TEMP_LINK"
        if [[ "$MOVED" == true ]]; then
            test ! -L "$OLD_MEDIA" || rm -f -- "$OLD_MEDIA"
            test -e "$OLD_MEDIA" || mv -- "$MEDIA_BACKUP" "$OLD_MEDIA"
        fi
        exit "$status"
    }
    trap 'restore_old_media $?' ERR
    trap 'restore_old_media 129' HUP
    trap 'restore_old_media 130' INT
    trap 'restore_old_media 143' TERM

    test -d "$OLD_MEDIA" && test ! -L "$OLD_MEDIA"
    test ! -e "$MEDIA_BACKUP" && test ! -L "$MEDIA_BACKUP"
    sudo rsync -a --chown=admin:labhub-media --chmod=D2750,F640 -- "$OLD_MEDIA/" /var/lib/labhub/media/
    sudo rsync -a --dry-run --itemize-changes --chown=admin:labhub-media --chmod=D2750,F640 -- "$OLD_MEDIA/" /var/lib/labhub/media/ | tee /tmp/labhub-media-final-delta.txt
    test ! -s /tmp/labhub-media-final-delta.txt
    ln -s -- /var/lib/labhub/media "$TEMP_LINK"
    mv -- "$OLD_MEDIA" "$MEDIA_BACKUP"
    MOVED=true
    mv -T -- "$TEMP_LINK" "$OLD_MEDIA"
    test "$(readlink -f -- "$OLD_MEDIA")" = /var/lib/labhub/media
    sudo -u admin test -w "$OLD_MEDIA"
    trap - ERR INT TERM HUP
)
```

Restore traffic dan lakukan satu upload/read terkontrol terhadap proses checkout lama
yang sama, masih tanpa restart:

```bash
sudo truncate -s 0 /etc/nginx/labhub-maintenance.conf
sudo nginx -t
sudo systemctl reload nginx
curl --fail --max-time 5 -H 'Host: <production-hostname>' http://127.0.0.1/ >/dev/null
sudo find /var/lib/labhub/media -type f -mmin -10 -print
curl --fail --head -H 'Host: <production-hostname>' 'http://127.0.0.1/media/<uploaded-test-file>'
```

Jika validasi gagal, block traffic lagi, sync target kembali ke backup tanpa
`--delete`, lalu restore directory lama. Jangan hapus backup tanpa owner approval:

```bash
printf 'return 503;\n' | sudo tee /etc/nginx/labhub-maintenance.conf >/dev/null
sudo nginx -t
sudo systemctl reload nginx
OLD_MEDIA=/home/admin/LabTif/ProjectLaboran/media
MEDIA_BACKUP=/home/admin/LabTif/ProjectLaboran/media.pre-persistent
sudo rsync -a --chown=admin:labhub-media --chmod=D2750,F640 -- /var/lib/labhub/media/ "$MEDIA_BACKUP/"
rm -f -- "$OLD_MEDIA"
mv -- "$MEDIA_BACKUP" "$OLD_MEDIA"
sudo truncate -s 0 /etc/nginx/labhub-maintenance.conf
sudo nginx -t
sudo systemctl reload nginx
```

## Root ownership dan baseline

Setelah media berhasil, pindahkan runner ke `/home/admin/LabTif/actions-runner` bila
belum berada di sana. Lakukan one-time ownership conversion. Hanya `incoming` dan
`actions-runner` yang tetap admin-writable:

```bash
sudo chown root:root /home/admin/LabTif
sudo chmod 0755 /home/admin/LabTif
sudo install -d -o root -g root -m 0755 /home/admin/LabTif/releases
sudo install -d -o admin -g admin -m 0750 /home/admin/LabTif/incoming
sudo install -d -o admin -g admin -m 0750 /home/admin/LabTif/actions-runner
if ! sudo test -e /home/admin/LabTif/.deploy-history; then
    sudo install -o root -g root -m 0600 /dev/null /home/admin/LabTif/.deploy-history
fi
sudo setfacl -m u:labhub-app:--x,u:labhub-build:--x,u:nginx:--x /home/admin
if test -e /home/admin/LabTif/production-venv.shared-backup; then
    sudo chown -R root:root /home/admin/LabTif/production-venv.shared-backup
    sudo chmod -R u=rwX,go=rX /home/admin/LabTif/production-venv.shared-backup
fi
sudo test "$(stat -c '%U:%G %a' /home/admin/LabTif)" = 'root:root 755'
sudo test "$(stat -c '%U:%G %a' /home/admin/LabTif/releases)" = 'root:root 755'
sudo test "$(stat -c '%U:%G %a' /home/admin/LabTif/.deploy-history)" = 'root:root 600'
sudo test "$(stat -c '%U:%G' /home/admin/LabTif/incoming)" = admin:admin
sudo test "$(stat -c '%U:%G' /home/admin/LabTif/actions-runner)" = admin:admin
```

Launcher membuka `.deploy-history` dengan `O_APPEND`, menulis satu record tervalidasi
per operasi, lalu `fsync`; file ini tidak di-truncate, dirotasi, atau dihapus oleh
cleanup deployment. Candidate build memakai directory sementara mode `0710`
`root:labhub-build` di bawah `releases`, sehingga `labhub-build` dapat traverse tetapi
`admin` dan `labhub-app` tidak dapat membaca atau menjalankannya.

Jadikan checkout lama read-only bagi admin/labhub-app, kecuali media external yang
dicapai melalui symlink:

```bash
sudo chown -R root:root /home/admin/LabTif/ProjectLaboran
sudo chmod -R u=rwX,go=rX /home/admin/LabTif/ProjectLaboran
sudo chown -h root:root /home/admin/LabTif/ProjectLaboran/media
sudo test "$(readlink -f /home/admin/LabTif/ProjectLaboran/media)" = /var/lib/labhub/media
sudo -u labhub-app test -r /home/admin/LabTif/ProjectLaboran/manage.py
sudo -u labhub-app test -x /home/admin/LabTif/ProjectLaboran/venv/bin/python
```

Setelah ownership base dikonversi dengan perintah pada bagian sebelumnya, buat link
baseline sebagai root. `current` menunjuk checkout lama dan `production-venv` selalu
menunjuk `current/venv`:

```bash
sudo ln -s /home/admin/LabTif/ProjectLaboran /home/admin/LabTif/.current.bootstrap
sudo mv -Tf /home/admin/LabTif/.current.bootstrap /home/admin/LabTif/current
if test -e /home/admin/LabTif/production-venv && test ! -L /home/admin/LabTif/production-venv; then
    sudo mv /home/admin/LabTif/production-venv /home/admin/LabTif/production-venv.shared-backup
fi
sudo ln -s /home/admin/LabTif/current/venv /home/admin/LabTif/.production-venv.bootstrap
sudo mv -Tf /home/admin/LabTif/.production-venv.bootstrap /home/admin/LabTif/production-venv
sudo chown -h root:root /home/admin/LabTif/current /home/admin/LabTif/production-venv
test "$(readlink -f /home/admin/LabTif/current)" = /home/admin/LabTif/ProjectLaboran
test "$(readlink -f /home/admin/LabTif/production-venv)" = /home/admin/LabTif/ProjectLaboran/venv
```

Verifikasi ABI server menggunakan stable production interpreter. Saat bootstrap,
path ini resolve ke venv checkout lama; setelah deployment, path yang sama resolve
ke venv per-release melalui `current`:

```bash
/home/admin/LabTif/production-venv/bin/python -c 'import sys; print(f"cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}")'
```

Output harus sama persis dengan GitHub repository variable `DEPLOY_PYTHON_ABI` dan
ABI interpreter manylinux yang dipakai untuk membangun protected artifact sebelum
rollout. Sebagai contoh saja, Python 3.11 menghasilkan `cp311-cp311`; jangan memakai
nilai contoh tersebut jika interpreter build atau server berbeda.

Jangan hapus checkout lama, v1 env, media backup, atau shared venv backup.

## Install launcher root-owned

Owner review `deployment/deploy_release.sh`, lalu install sekali. Workflow **tidak
boleh** menjalankan copy script yang di-download atau copy dalam workspace runner:

```bash
test -x /usr/bin/bash
sudo install -o root -g root -m 0755 deployment/deploy_release.sh /usr/local/sbin/projectlaboran-deploy
sudo test "$(stat -c '%U:%G %a' /usr/local/sbin/projectlaboran-deploy)" = 'root:root 755'
test "$(sed -n '1p' /usr/local/sbin/projectlaboran-deploy)" = '#!/usr/bin/bash'
sudo /usr/bin/bash -n /usr/local/sbin/projectlaboran-deploy
```

Launcher wajib `EUID=0`, tidak memakai `sudo`, menerima satu envelope normal, dan
hanya berjalan dari installed path. Shebang absolute `/usr/bin/bash` tidak bergantung
pada `PATH` atau `/usr/bin/env`. Sebelum parse, launcher stream-copy incoming
runner ke regular file `O_EXCL` dalam temp root-only dengan batas 800 MiB. Snapshot
immutable selama proses itulah yang diparse dan diverifikasi, sehingga perubahan
concurrent pada source runner tidak mengubah input setelah snapshot. Parser tar
streaming berhenti pada header keempat dan menolak link, device, duplicate, traversal,
extra entry, sparse/PAX metadata, truncated content, size/mode tidak aman, serta total
di atas batas. Root Python helper memakai `/usr/bin/python3 -I` agar tidak import dari
workspace runner; `gh` dan `curl` berjalan dengan environment bersih. Protected archive
baru diekstrak setelah policy attestation sukses.

## Preflight v1 sebagai labhub-app

Jalankan one-shot check sebelum mengubah unit. Ini memuat v1 env sebagai root,
menjalankan trusted old checkout melalui `runuser labhub-app`, memeriksa media write,
dan tidak restart Daphne:

```bash
sudo /usr/local/sbin/projectlaboran-deploy --check-baseline
```

## Unit Daphne

Setelah preflight sukses, ubah unit. `current.env` masih menunjuk v1, sehingga config
v1 tidak diganti sebelum protected activation:

```ini
[Service]
User=labhub-app
Group=labhub-app
UMask=0027
WorkingDirectory=/home/admin/LabTif/current
EnvironmentFile=/etc/labhub/current.env
ExecStart=/home/admin/LabTif/production-venv/bin/python -m daphne -b 127.0.0.1 -p 8000 project_laboran.asgi:application
NoNewPrivileges=true
ProtectProc=invisible
```

Reload definisi saja. Jangan stop/restart Daphne sebelum artifact protected pertama:

```bash
sudo /usr/bin/systemctl daemon-reload
sudo /usr/bin/systemctl is-active --quiet projectlaboran-daphne
test "$(readlink -f /home/admin/LabTif/current)" = /home/admin/LabTif/ProjectLaboran
test "$(readlink -f /etc/labhub/current.env)" = /etc/labhub/labhub-v1.env
```

Jika restart tak terduga terjadi, path code/venv lama dan v1 env sudah valid untuk
`labhub-app`. Restart yang direncanakan pertama dilakukan root launcher hanya setelah
verified release siap dan kedua link `current`/`current.env` telah dipindahkan.

## Sudoers runner

Hapus rule systemctl/manage lama. Runner `admin` hanya mendapat satu exact command
tanpa password:

```bash
printf '%s\n' \
  'Defaults:admin secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"' \
  'admin ALL=(root) NOPASSWD: /usr/local/sbin/projectlaboran-deploy /home/admin/LabTif/incoming/projectlaboran.deploy.tar' \
  | sudo tee /etc/sudoers.d/projectlaboran-deploy >/dev/null
sudo chown root:root /etc/sudoers.d/projectlaboran-deploy
sudo chmod 0440 /etc/sudoers.d/projectlaboran-deploy
sudo /usr/sbin/visudo -cf /etc/sudoers.d/projectlaboran-deploy
sudo grep -Fx 'Defaults:admin secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"' /etc/sudoers.d/projectlaboran-deploy
sudo -n -l /usr/local/sbin/projectlaboran-deploy /home/admin/LabTif/incoming/projectlaboran.deploy.tar >/dev/null
```

Jangan grant systemctl, shell, manage.py, arbitrary launcher path, wildcard argument,
atau bentuk `--rollback` kepada runner. Periksa bahwa output `sudo -n -l` hanya memuat
exact normal command di atas. Owner rollback memakai authenticated sudo dari sesi
owner dan **tidak boleh** ditambahkan ke sudoers NOPASSWD runner.
Scoped `secure_path` adalah defense in depth untuk command internal, bukan pengganti
shebang absolute dan absolute executable paths milik launcher.
Self-hosted runner wajib dedicated hanya untuk repository ini. Workflow deployment
wajib memakai GitHub Environment approval dengan required reviewer, protected `main`
yang melarang direct push, serta CODEOWNERS required review untuk
`.github/workflows/`; workflow harus menolak fork/third-party arbitrary jobs. Runner tidak
menerima production env dan tidak dapat menulis executed release code. Dedicated
`labhub-app` UID mencegah `admin` membaca `/proc/<app-pid>/environ`.

## Task 7 handoff

Task 7 mem-pin `pip-tools`, membuat hash-locked `requirements.lock`, mengunduh exact
manylinux wheels ke `wheelhouse/`, lalu memasukkan keduanya ke protected archive
sebelum GitHub-hosted attestation dibuat. Task tersebut menulis lowercase source SHA,
membuat envelope, lalu menaruhnya atomik pada fixed incoming path. Workflow hanya
memanggil installed launcher:

```bash
sudo -n /usr/local/sbin/projectlaboran-deploy /home/admin/LabTif/incoming/projectlaboran.deploy.tar
```

Setelah protected deployment pertama, validasi Nginx terhadap asset release aktif
tanpa public IP. Ganti `SERVER_NAME` dengan `server_name` TLS production yang sudah
memiliki certificate valid:

```bash
CURRENT_RELEASE=$(readlink -f /home/admin/LabTif/current)
[[ "$CURRENT_RELEASE" =~ ^/home/admin/LabTif/releases/[0-9a-f]{40}$ ]]
STATIC_ASSET="$CURRENT_RELEASE/staticfiles/admin/css/base.css"
sudo test -f "$STATIC_ASSET"
sudo restorecon -F "$CURRENT_RELEASE"
sudo restorecon -RF "$CURRENT_RELEASE/staticfiles"
sudo -u nginx test -x /home/admin
sudo -u nginx test -x /home/admin/LabTif
sudo -u nginx test -x "$CURRENT_RELEASE"
sudo -u nginx test -r "$STATIC_ASSET"
if sudo -u nginx test -w "$CURRENT_RELEASE/staticfiles"; then exit 1; fi
if sudo -u nginx test -w "$STATIC_ASSET"; then exit 1; fi
sudo nginx -t
sudo systemctl reload nginx
SERVER_NAME='<production-server-name>'
curl --fail --silent --show-error \
  --resolve "${SERVER_NAME}:443:127.0.0.1" \
  "https://${SERVER_NAME}/static/admin/css/base.css" >/dev/null
```

Nginx alias mengikuti `current/staticfiles`; atomic current switch saat deploy atau
rollback otomatis memilih static asset dari release code yang sama. Nginx tidak
mendapat write pada releases atau staticfiles.

## Transaction dan rollback

Launcher memegang `/home/admin/LabTif/.deploy.lock`. Journal root-owned mencatat kind,
SHA/release, previous code, previous env, target v2 env, replacement backup, dan
phase. Sebelum restart, launcher switch `current` dan `/etc/labhub/current.env`
secara terpisah tetapi di dalam transaction yang sama. Crash/signal di antaranya
mengembalikan **keduanya**, lalu restart dan identity/health-check target lama.

Protected release diekstrak streaming dengan jumlah entry, size per-entry, dan total
uncompressed yang dibatasi. Candidate berada di temp private `root:labhub-build 0710`.
Root membuat directory `venv` milik `labhub-build`; user tersebut menjalankan
`python3 -m venv` dan install hanya dari wheelhouse dengan `--no-index` serta
`--require-hashes`. Masih di candidate private, `labhub-build` menjalankan
`collectstatic` dengan `env -i`, safe PATH/HOME, placeholder `SECRET_KEY`,
`DEBUG=False`, dan `LABHUB_LICENSE_ENFORCED=False`. Tidak ada v1/v2 env, database
credential, license key, atau production secret yang dibaca. Static output wajib
hanya regular file/directory milik build UID,
tanpa symlink/device/hardlink, dan lolos batas entry, per-file, serta total size.

Setelah itu seluruh candidate recursively di-seal `root:root`, group/other write
dihapus, top directory menjadi root-only `0700`, dan tree divalidasi sebelum rename
publication; mode release menjadi `0755` hanya setelah berada pada path final
root-owned. `labhub-app` tidak pernah memiliki candidate/staticfiles atau menerima FD
writable. Baru setelah publication dan SELinux relabel, root membaca v2 env untuk
read-only `check` dan migration melalui `runuser labhub-app`. Console script venv
tidak dipakai setelah candidate rename; systemd dan launcher selalu memanggil
`venv/bin/python` secara langsung.

Sebelum build, sebelum publication, dan tepat sebelum activation, live GitHub
main-head harus tetap sama dengan SHA envelope. Record `consumed` ditulis setelah
attestation/freshness awal dan tidak
dihapus saat build gagal, sehingga exact envelope/archive tidak dapat dicoba ulang;
Task 7 harus menghasilkan envelope baru dari HEAD terbaru. Record `deployed` dan
marker digest ditulis setelah restart sehat. Normal deploy juga menolak SHA yang
sudah aktif; pemeriksaan/rollback release aktif memakai protocol owner, bukan replay
envelope runner.

Health menerima HTTP status di bawah 500. Service identity memerlukan active
`MainPID`, UID `labhub-app`, root-owned non-writable executable, Daphne cmdline, dan
`/proc/<MainPID>/cwd` yang sama dengan target `current`. Rollback owner ke target yang
sudah aktif sukses hanya jika marker root-owned, current env v2, identity, dan health
semuanya cocok.

Phase `committed` tidak pernah eligible untuk rollback. Startup hanya memverifikasi
identity/marker/deployment-state/health dan menyelesaikan cleanup; kegagalan mempertahankan journal
dan return nonzero. Phase incomplete mengembalikan previous code **dan** previous env.
Signal HUP/INT/TERM mempertahankan status nonzero.

Rollback manual harus memakai protocol launcher yang sama, bukan raw `ln`/`mv`:

```bash
ROLLBACK_SHA='<40-lowercase-hex-protected-release-sha>'
sudo /usr/local/sbin/projectlaboran-deploy --rollback "$ROLLBACK_SHA"
```

Target wajib direct child release dengan marker valid. Mode ini memakai lock, journal,
dual-link switch, restart, identity, health, dan committed cleanup yang sama. Database
migration tidak dibalik otomatis; gunakan migration backward-compatible dan recovery
database terpisah.

Release aktif dan dua inactive terbaru dipertahankan. Cleanup tidak menghapus current,
release target, path di luar root-owned releases, checkout lama, env v1, atau media.

## Retirement v1 dengan owner approval

Jangan retire v1 setelah protected deploy pertama saja. Tunggu current protected
sehat dan minimal satu protected release lain dengan marker tersedia untuk rollback:

```bash
test "$(readlink -f /etc/labhub/current.env)" = /etc/labhub/labhub-v2.env
test "$(readlink -f /home/admin/LabTif/current)" != /home/admin/LabTif/ProjectLaboran
test ! -e /home/admin/LabTif/.deploy-transaction
count=$(sudo find /home/admin/LabTif/releases -mindepth 2 -maxdepth 2 -type f -name .deploy-success | wc -l)
test "$count" -ge 2
```

Setelah backup dan owner approval, pindahkan v1 env dan checkout lama ke archive
root-only; jangan delete langsung. Hapus verification secret hanya dari retired copy
setelah kebutuhan recovery berakhir:

```bash
RETIRE_DIR=/root/labhub-retired-$(date +%Y%m%d)
sudo install -d -o root -g root -m 0700 "$RETIRE_DIR"
sudo mv /etc/labhub/labhub-v1.env "$RETIRE_DIR/labhub-v1.env"
sudo mv /home/admin/LabTif/ProjectLaboran "$RETIRE_DIR/ProjectLaboran"
sudo sed -i '/^LABHUB_LICENSE_VERIFICATION_SECRET=/d' "$RETIRE_DIR/labhub-v1.env"
sudo chmod 0600 "$RETIRE_DIR/labhub-v1.env"
```

`current.env` tetap v2 dan protected rollback tidak memerlukan v1. Retired archive,
media backup, dan database backup dihapus hanya melalui keputusan owner terpisah.
