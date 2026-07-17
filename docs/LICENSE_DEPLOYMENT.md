# LabHub License Deployment

License Ed25519 versi 2 mengunci aplikasi ke fingerprint server. Public key untuk
verifikasi sudah tertanam di artifact. Private key tetap hanya di laptop owner dan
tidak pernah disimpan di server production.

## Generate license di laptop owner

Ambil fingerprint AlmaLinux target:

```bash
cat /etc/machine-id
```

Gunakan file private key Ed25519 di laptop owner melalui
`LABHUB_LICENSE_PRIVATE_KEY_FILE`. Jangan unggah file ini ke Git, CI artifact, atau
server production.

PowerShell:

```powershell
$env:LABHUB_LICENSE_PRIVATE_KEY_FILE=(Resolve-Path .secrets/labhub-license-private.ed25519.pem)
python manage.py generate_labhub_license --customer "Lab FTI" --fingerprint "<machine-id-server>" --expires-on 2030-01-31
```

Bash:

```bash
export LABHUB_LICENSE_PRIVATE_KEY_FILE="$HOME/.secrets/labhub-license-private.ed25519.pem"
python manage.py generate_labhub_license --customer "Lab FTI" --fingerprint "<machine-id-server>" --expires-on 2030-01-31
```

Output command adalah nilai `LABHUB_LICENSE_KEY` versi 2. Dokumentasi ini tidak
memuat license production atau private key sebenarnya.

## Persistent media

Artifact release tidak pernah berisi upload pada direktori `media/`. Semua upload
harus berada di luar release agar pergantian atau cleanup release tidak menghapus
data pengguna. Buat lokasi persistent berikut satu kali:

```bash
sudo install -d -o admin -g admin -m 0750 /var/lib/labhub
sudo install -d -o admin -g admin -m 0750 /var/lib/labhub/media
sudo test -d /home/admin/LabTif/ProjectLaboran/media
sudo rsync -a --ignore-existing --chown=admin:admin --chmod=D750,F640 -- /home/admin/LabTif/ProjectLaboran/media/ /var/lib/labhub/media/
sudo find /var/lib/labhub/media -maxdepth 1 -printf '%M %u:%g %p\n'
```

Trailing slash pada sumber `media/` penting: isinya disalin langsung ke direktori
tujuan. Jangan hapus `/home/admin/LabTif/ProjectLaboran/media/` setelah copy. Owner
harus memverifikasi jumlah file, upload baru, backup, dan rollback terlebih dahulu;
penghapusan sumber lama adalah keputusan manual terpisah.

## Environment production

Buat direktori dan file environment sebagai `root:root`. File harus mode `0600`:

```bash
sudo install -d -o root -g root -m 0700 /etc/labhub
sudo test -e /etc/labhub/labhub.env || sudo install -o root -g root -m 0600 /dev/null /etc/labhub/labhub.env
sudo chown root:root /etc/labhub/labhub.env
sudo chmod 0600 /etc/labhub/labhub.env
sudoedit /etc/labhub/labhub.env
sudo stat -c '%U:%G %a %n' /etc/labhub/labhub.env
```

Isi semua variabel runtime production yang sudah digunakan aplikasi. Gunakan nilai
production yang sebenarnya di server, bukan placeholder di bawah:

```env
SECRET_KEY=<existing-production-secret-key>
DEBUG=False
ALLOWED_HOSTS=<existing-production-hosts>
DB_NAME=<existing-production-database>
DB_USER=<existing-production-database-user>
DB_PASSWORD=<existing-production-database-password>
DB_HOST=<existing-production-database-host>
DB_PORT=3306
MEDIA_ROOT=/var/lib/labhub/media
LABHUB_LICENSE_ENFORCED=True
LABHUB_LICENSE_KEY=<license-v2-dari-laptop-owner>
```

Pertahankan juga secret runtime yang memang dipakai, misalnya API, email, Redis,
atau integrasi lain. `LABHUB_LICENSE_FINGERPRINT` boleh ditambahkan jika license
dibuat dengan override selain `/etc/machine-id`. Server hanya menyimpan
`LABHUB_LICENSE_ENFORCED`, `LABHUB_LICENSE_KEY`, dan optional fingerprint override
untuk licensing; server tidak menyimpan private key, signing key, atau verification
secret.

Ganti license v1 lama dengan output v2 dan hapus variabel lama:

```bash
sudo sed -i '/^LABHUB_LICENSE_VERIFICATION_SECRET=/d' /etc/labhub/labhub.env
sudoedit /etc/labhub/labhub.env
sudo grep -q '^MEDIA_ROOT=/var/lib/labhub/media$' /etc/labhub/labhub.env
```

Proses deployment yang menjalankan migration harus menerima environment runtime
yang sama. Pada self-hosted runner khusus deployment, tambahkan
`EnvironmentFile=/etc/labhub/labhub.env` melalui systemd drop-in unit runner, lalu
restart runner sebelum rollout. Jangan mencetak environment ke log. Script deploy
akan berhenti sebelum publication jika `MEDIA_ROOT` tidak bernilai
`/var/lib/labhub/media` atau tidak writable oleh `admin`.

## Baseline symlink tanpa outage

Checkout lama sudah memiliki `/home/admin/LabTif/ProjectLaboran/venv`. Sebelum
mengubah atau me-reload unit Daphne, buat baseline berikut sebagai user `admin`:

```bash
sudo install -d -o admin -g admin -m 0755 /home/admin/LabTif
sudo install -d -o admin -g admin -m 0755 /home/admin/LabTif/releases
test -x /home/admin/LabTif/ProjectLaboran/venv/bin/python
cd /home/admin/LabTif
test ! -e .current.bootstrap && test ! -L .current.bootstrap
ln -s /home/admin/LabTif/ProjectLaboran .current.bootstrap
mv -Tf .current.bootstrap current
test "$(readlink -f current)" = /home/admin/LabTif/ProjectLaboran
if test -e production-venv && test ! -L production-venv; then
    test ! -e production-venv.shared-backup
    mv production-venv production-venv.shared-backup
fi
if test ! -e production-venv && test ! -L production-venv; then
    ln -s /home/admin/LabTif/current/venv production-venv
fi
test "$(readlink production-venv)" = /home/admin/LabTif/current/venv
test "$(readlink -f production-venv)" = /home/admin/LabTif/ProjectLaboran/venv
```

Jangan hapus `production-venv.shared-backup` atau checkout lama sampai owner
menyetujui cleanup. Setiap release baru membuat venv sendiri di
`releases/<github-sha>/venv`. Path public `/home/admin/LabTif/production-venv`
tetap berupa symlink ke `/home/admin/LabTif/current/venv`; pergantian `current`
karena deploy atau rollback mengganti kode dan interpreter secara bersamaan.

Verifikasi ABI Python baseline. Nilainya harus sama dengan ABI artifact dari
workflow build, misalnya `cp312-cp312`:

```bash
/home/admin/LabTif/current/venv/bin/python -c "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}')"
python3 -c "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}')"
```

## Sudo least privilege

Script memakai executable AlmaLinux `/usr/bin/systemctl`. Verifikasi path sebelum
memasang rule:

```bash
test "$(command -v systemctl)" = /usr/bin/systemctl
test "$(command -v visudo)" = /usr/sbin/visudo
```

Pasang `/etc/sudoers.d/projectlaboran-deploy` hanya dengan operasi yang diperlukan:

```bash
printf '%s\n' \
  'admin ALL=(root) NOPASSWD: /usr/bin/systemctl daemon-reload' \
  'admin ALL=(root) NOPASSWD: /usr/bin/systemctl restart projectlaboran-daphne' \
  'admin ALL=(root) NOPASSWD: /usr/bin/systemctl stop projectlaboran-daphne' \
  'admin ALL=(root) NOPASSWD: /usr/bin/systemctl is-active --quiet projectlaboran-daphne' \
  'admin ALL=(root) NOPASSWD: /usr/bin/systemctl show projectlaboran-daphne --property=LoadState --value' \
  | sudo tee /etc/sudoers.d/projectlaboran-deploy >/dev/null
sudo chown root:root /etc/sudoers.d/projectlaboran-deploy
sudo chmod 0440 /etc/sudoers.d/projectlaboran-deploy
sudo /usr/sbin/visudo -cf /etc/sudoers.d/projectlaboran-deploy
```

Validasi non-interaktif sebagai user `admin`. Perintah `sudo -l` hanya memeriksa
otorisasi dan tidak me-restart service:

```bash
sudo -n -l /usr/bin/systemctl daemon-reload >/dev/null
sudo -n -l /usr/bin/systemctl restart projectlaboran-daphne >/dev/null
sudo -n -l /usr/bin/systemctl stop projectlaboran-daphne >/dev/null
sudo -n -l /usr/bin/systemctl is-active --quiet projectlaboran-daphne >/dev/null
sudo -n -l /usr/bin/systemctl show projectlaboran-daphne --property=LoadState --value >/dev/null
test "$(sudo -n /usr/bin/systemctl show projectlaboran-daphne --property=LoadState --value)" = loaded
```

Jangan gunakan `NOPASSWD: ALL`. Deploy melakukan seluruh preflight sudo di atas
sebelum publication, migration, atau pergantian `current`.

## Konfigurasi systemd

Setelah baseline symlink dan environment siap, ubah
`/etc/systemd/system/projectlaboran-daphne.service`:

```ini
[Service]
User=admin
Group=admin
WorkingDirectory=/home/admin/LabTif/current
EnvironmentFile=/etc/labhub/labhub.env
ExecStart=/home/admin/LabTif/production-venv/bin/python -m daphne -b 0.0.0.0 -p 8000 project_laboran.asgi:application
```

Reload unit, tetapi jangan restart Daphne sebelum artifact pertama. Baseline
`current` tetap menunjuk checkout lama sehingga tidak ada window path yang hilang:

```bash
sudo /usr/bin/systemctl daemon-reload
readlink -f /home/admin/LabTif/current
readlink -f /home/admin/LabTif/production-venv
```

## Model deployment dan rollback otomatis

Script memegang `flock` pada `/home/admin/LabTif/.deploy.lock`, memvalidasi archive,
dan mempublikasikan candidate ke `/home/admin/LabTif/releases/<github-sha>` tanpa
mengubah runtime aktif. Candidate membuat venv final di `venv/`, menginstal
requirements, menjalankan migration, dan menjalankan `collectstatic`. Hanya setelah
semua langkah tersebut berhasil, symlink `current` diganti secara atomik.

Sesudah switch, script menjalankan `daemon-reload`, restart, `is-active`, lalu
mencoba `http://127.0.0.1:8000/` hingga 15 kali. Respons HTTP di bawah 500 dianggap
sehat; network failure atau status 500 ke atas memicu rollback. Error maupun signal
`TERM`, `INT`, dan `HUP` setelah switch mengembalikan `current` sebelumnya secara
atomik dan me-restart service. Signal sebelum switch tidak menyentuh service aktif.

Sisa `.deploy-*`, `.failed-*`, dan `.replaced-*` direkonsiliasi hanya saat lock
dipegang. Cleanup tidak pernah menghapus target `current`, path di luar `releases`,
atau release yang sedang dideploy. Setelah deployment sehat, release aktif dan dua
release inactive terbaru dipertahankan. Cleanup failure hanya menjadi warning.

Rerun SHA yang sudah aktif bersifat idempotent: script memverifikasi `is-active` dan
health endpoint lalu sukses tanpa mengganti atau menghapus release. SHA yang ada
tetapi inactive diganti melalui staging dengan backup yang dapat dipulihkan.

Migration dijalankan sebelum switch dan tidak di-rollback otomatis. Gunakan
migration yang backward-compatible. Rollback kode tidak sama dengan rollback schema
atau data; perubahan database yang tidak kompatibel memerlukan recovery terpisah.

## Rollback manual dengan lock

Pilih SHA release yang masih tersedia. Ganti placeholder, lalu jalankan seluruh
blok sebagai user `admin`. Lock mencakup validasi target, switch, restart, dan health
check. Jika langkah setelah switch gagal, trap mengembalikan target sebelumnya:

```bash
(
    set -Eeuo pipefail
    ROLLBACK_SHA='<40-character-git-sha>'
    BASE_DIR=/home/admin/LabTif
    CURRENT_LINK="$BASE_DIR/current"
    TARGET="$BASE_DIR/releases/$ROLLBACK_SHA"
    TEMP_LINK="$BASE_DIR/.current.rollback.$$"
    PREVIOUS=''
    SWITCHED=false
    TEMP_CREATED=false

    exec 9>"$BASE_DIR/.deploy.lock"
    flock -n 9
    [[ "$ROLLBACK_SHA" =~ ^[0-9a-fA-F]{40}$ ]]
    test "$(dirname -- "$TARGET")" = "$BASE_DIR/releases"
    test -d "$TARGET" && test ! -L "$TARGET"
    test "$(readlink -f -- "$TARGET")" = "$TARGET"
    test -f "$TARGET/manage.py"
    test -x "$TARGET/venv/bin/python"
    PREVIOUS=$(readlink -f -- "$CURRENT_LINK")

    rollback_manual() {
        status=${1:-$?}
        trap - ERR
        trap '' TERM INT HUP
        set +e
        if [[ "$TEMP_CREATED" == true ]]; then
            rm -f -- "$TEMP_LINK"
        fi
        active=$(readlink -f -- "$CURRENT_LINK" 2>/dev/null || true)
        if [[ -n "$PREVIOUS" && ( "$SWITCHED" == true || "$active" == "$TARGET" ) ]]; then
            ln -s -- "$PREVIOUS" "$TEMP_LINK" && mv -Tf -- "$TEMP_LINK" "$CURRENT_LINK"
            sudo -n /usr/bin/systemctl restart projectlaboran-daphne
        fi
        exit "$status"
    }
    trap 'rollback_manual $?' ERR
    trap 'rollback_manual 129' HUP
    trap 'rollback_manual 130' INT
    trap 'rollback_manual 143' TERM

    test ! -e "$TEMP_LINK" && test ! -L "$TEMP_LINK"
    TEMP_CREATED=true
    ln -s -- "$TARGET" "$TEMP_LINK"
    mv -Tf -- "$TEMP_LINK" "$CURRENT_LINK"
    TEMP_CREATED=false
    SWITCHED=true
    test "$(readlink -f -- /home/admin/LabTif/production-venv)" = "$TARGET/venv"
    sudo -n /usr/bin/systemctl daemon-reload
    sudo -n /usr/bin/systemctl restart projectlaboran-daphne
    sudo -n /usr/bin/systemctl is-active --quiet projectlaboran-daphne

    healthy=false
    for attempt in {1..15}; do
        if status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --connect-timeout 2 --max-time 5 http://127.0.0.1:8000/) \
            && [[ "$status" =~ ^[0-9]{3}$ ]] && ((10#$status < 500)); then
            healthy=true
            break
        fi
        sleep 2
    done
    [[ "$healthy" == true ]]
    trap - ERR TERM INT HUP
    readlink -f -- "$CURRENT_LINK"
)
```

Rollback manual ini juga tidak membalik migration database. Evaluasi kompatibilitas
schema dan siapkan recovery database sebelum memilih release lama.

## Catatan keamanan

Proteksi artifact bukan pengganti pembatasan akses server. Batasi akses shell,
runner, sudoers, environment production, backup, dan direktori persistent media.
