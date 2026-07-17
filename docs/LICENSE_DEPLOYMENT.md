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
data pengguna. Buat group baca khusus untuk runtime `admin` dan Nginx, lalu buat
lokasi persistent dengan setgid. Perintah berikut mengasumsikan user proxy AlmaLinux
adalah `nginx`:

```bash
getent group labhub-media >/dev/null || sudo groupadd --system labhub-media
sudo usermod -aG labhub-media admin
sudo usermod -aG labhub-media nginx
sudo install -d -o root -g labhub-media -m 0750 /var/lib/labhub
sudo install -d -o admin -g labhub-media -m 2750 /var/lib/labhub/media
sudo test -d /home/admin/LabTif/ProjectLaboran/media
sudo rsync -a --chown=admin:labhub-media --chmod=D2750,F640 -- /home/admin/LabTif/ProjectLaboran/media/ /var/lib/labhub/media/
sudo find /var/lib/labhub/media -maxdepth 1 -printf '%M %u:%g %p\n'
```

Trailing slash pada sumber `media/` penting: isinya disalin langsung ke direktori
tujuan. Copy awal boleh dilakukan saat aplikasi masih aktif dan sengaja tidak
memakai `--delete`. Cutover authoritative tetap wajib dilakukan dalam maintenance
window setelah konfigurasi proxy siap. Jangan hapus sumber lama; owner
harus menyetujui cleanup secara terpisah setelah backup dan rollback diverifikasi.

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

Jangan menambahkan `/etc/labhub/labhub.env` atau nilainya ke service self-hosted
runner, workflow, artifact, maupun log. Hanya unit Daphne dan restricted launcher
root-owned di bawah yang boleh memuat file tersebut.

## Serving media dengan Nginx dan SELinux

Django/Daphne dengan `DEBUG=False` tidak melayani `/media/` untuk production.
Reverse proxy harus melayani file dari `/var/lib/labhub/media/`. Contoh blok Nginx:

```nginx
# Di dalam server block production:
include /etc/nginx/labhub-maintenance.conf;

location /media/ {
    alias /var/lib/labhub/media/;
    autoindex off;
    add_header X-Content-Type-Options nosniff always;
}
```

Persistenkan label SELinux yang mengizinkan Nginx membaca media. Package
`policycoreutils-python-utils` menyediakan `semanage` pada AlmaLinux:

```bash
sudo dnf install -y policycoreutils-python-utils
sudo test -e /etc/nginx/labhub-maintenance.conf || sudo install -o root -g root -m 0644 /dev/null /etc/nginx/labhub-maintenance.conf
sudo semanage fcontext -a -t httpd_sys_content_t '/var/lib/labhub/media(/.*)?'
sudo restorecon -Rv /var/lib/labhub/media
sudo -u nginx test -x /var/lib/labhub/media
sudo -u nginx find /var/lib/labhub/media -type f -print -quit | xargs -r sudo -u nginx test -r
sudo nginx -t
sudo systemctl reload nginx
curl --fail --head -H 'Host: <production-hostname>' 'http://127.0.0.1/media/<known-test-file>'
```

Gunakan hostname virtual host production, bukan public IP. Jika server tidak memakai
Nginx, konfigurasi proxy atau media server ekuivalen, permission group, dan policy
SELinux yang setara wajib selesai dan tervalidasi sebelum rollout.

## Maintenance window untuk cutover media

Daphne checkout lama harus tetap berjalan tanpa stop atau restart. Jadwalkan window
write-free dan blok traffic pada reverse proxy. Pastikan port Daphne `8000` tidak
dipublikasikan oleh firewalld; dari host lain di jaringan, koneksi langsung ke
`http://<server-private-address>:8000/` juga harus gagal. Hanya Nginx lokal yang boleh
mengakses port tersebut:

```bash
if sudo firewall-cmd --query-port=8000/tcp; then
    sudo firewall-cmd --remove-port=8000/tcp
fi
if sudo firewall-cmd --permanent --query-port=8000/tcp; then
    sudo firewall-cmd --permanent --remove-port=8000/tcp
fi
sudo firewall-cmd --reload
if sudo firewall-cmd --query-port=8000/tcp; then
    printf 'Port 8000 is still exposed.\n' >&2
    exit 1
fi
curl --fail --max-time 5 http://127.0.0.1:8000/ >/dev/null
```

Dari host lain pada jaringan server, perintah berikut wajib gagal:

```bash
if curl --silent --show-error --max-time 3 'http://<server-private-address>:8000/' >/dev/null; then
    printf 'Direct Daphne port is externally reachable.\n' >&2
    exit 1
fi
```

Aktifkan maintenance response pada production server block. Perintah ini memblokir
request melalui Nginx dengan status 503 tanpa menghentikan Daphne:

```bash
printf 'return 503;\n' | sudo tee /etc/nginx/labhub-maintenance.conf >/dev/null
sudo nginx -t
sudo systemctl reload nginx
status=$(curl --silent --output /dev/null --write-out '%{http_code}' -H 'Host: <production-hostname>' http://127.0.0.1/)
test "$status" = 503
```

Dengan traffic tetap diblokir, lakukan final authoritative sync dan wajib pastikan
dry-run tidak menghasilkan delta. Lalu rename direktori media lama menjadi backup
tetap dan publish symlink dengan rename pada filesystem checkout yang sama. Trap
mengembalikan direktori lama jika cutover lokal gagal sebelum blok selesai:

```bash
(
    set -Eeuo pipefail
    OLD_MEDIA=/home/admin/LabTif/ProjectLaboran/media
    MEDIA_BACKUP=/home/admin/LabTif/ProjectLaboran/media.pre-persistent
    TEMP_MEDIA_LINK=/home/admin/LabTif/ProjectLaboran/.media.persistent.$$
    OLD_MEDIA_MOVED=false

    rollback_local_cutover() {
        status=${1:-$?}
        trap - ERR INT TERM HUP
        set +e
        test ! -L "$TEMP_MEDIA_LINK" || rm -f -- "$TEMP_MEDIA_LINK"
        if [[ "$OLD_MEDIA_MOVED" == true ]]; then
            test ! -L "$OLD_MEDIA" || rm -f -- "$OLD_MEDIA"
            test -e "$OLD_MEDIA" || mv -- "$MEDIA_BACKUP" "$OLD_MEDIA"
        fi
        exit "$status"
    }
    trap 'rollback_local_cutover $?' ERR
    trap 'rollback_local_cutover 129' HUP
    trap 'rollback_local_cutover 130' INT
    trap 'rollback_local_cutover 143' TERM

    test -d "$OLD_MEDIA" && test ! -L "$OLD_MEDIA"
    test ! -e "$MEDIA_BACKUP" && test ! -L "$MEDIA_BACKUP"
    test ! -e "$TEMP_MEDIA_LINK" && test ! -L "$TEMP_MEDIA_LINK"
    sudo rsync -a --chown=admin:labhub-media --chmod=D2750,F640 -- "$OLD_MEDIA/" /var/lib/labhub/media/
    sudo rsync -a --dry-run --itemize-changes --chown=admin:labhub-media --chmod=D2750,F640 -- "$OLD_MEDIA/" /var/lib/labhub/media/ | tee /tmp/labhub-media-final-delta.txt
    test ! -s /tmp/labhub-media-final-delta.txt
    ln -s -- /var/lib/labhub/media "$TEMP_MEDIA_LINK"
    mv -- "$OLD_MEDIA" "$MEDIA_BACKUP"
    OLD_MEDIA_MOVED=true
    mv -T -- "$TEMP_MEDIA_LINK" "$OLD_MEDIA"
    test "$(readlink -f -- "$OLD_MEDIA")" = /var/lib/labhub/media
    sudo -u admin test -w "$OLD_MEDIA"
    sudo restorecon -Rv /var/lib/labhub/media
    trap - ERR INT TERM HUP
)
```

Jangan gunakan `--delete`: source lama tetap tersimpan sebagai
`media.pre-persistent` sampai owner menyetujui penghapusan. Kosongkan maintenance
include dan reload Nginx untuk membuka traffic, tetapi pertahankan maintenance window
agar hanya owner melakukan upload/read uji terhadap checkout **lama yang masih
berjalan**:

```bash
sudo truncate -s 0 /etc/nginx/labhub-maintenance.conf
sudo nginx -t
sudo systemctl reload nginx
curl --fail --max-time 5 -H 'Host: <production-hostname>' http://127.0.0.1/ >/dev/null
sudo find /var/lib/labhub/media -type f -mmin -10 -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n'
curl --fail --head -H 'Host: <production-hostname>' 'http://127.0.0.1/media/<uploaded-test-file>'
```

Lakukan satu upload terkontrol melalui UI/API dan pastikan file dapat dibaca kembali
melalui URL Nginx di atas. Jangan buka window untuk user lain sebelum validasi selesai.
Jika upload/read gagal, blok traffic lagi lalu rollback symlink selama maintenance
window. Sync balik tanpa `--delete` mempertahankan upload uji yang mungkin sudah
masuk ke persistent target:

```bash
printf 'return 503;\n' | sudo tee /etc/nginx/labhub-maintenance.conf >/dev/null
sudo nginx -t
sudo systemctl reload nginx
OLD_MEDIA=/home/admin/LabTif/ProjectLaboran/media
MEDIA_BACKUP=/home/admin/LabTif/ProjectLaboran/media.pre-persistent
test "$(readlink -f -- "$OLD_MEDIA")" = /var/lib/labhub/media
test -d "$MEDIA_BACKUP" && test ! -L "$MEDIA_BACKUP"
sudo rsync -a --chown=admin:labhub-media --chmod=D2750,F640 -- /var/lib/labhub/media/ "$MEDIA_BACKUP/"
rm -f -- "$OLD_MEDIA"
mv -- "$MEDIA_BACKUP" "$OLD_MEDIA"
sudo truncate -s 0 /etc/nginx/labhub-maintenance.conf
sudo nginx -t
sudo systemctl reload nginx
```

Protected rollout hanya boleh dilanjutkan setelah upload/read checkout lama berhasil.
Migration database terpisah dan tidak dibalik oleh media rollback.

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

## Restricted manage launcher

Runner tidak boleh membaca environment production. Owner memasang launcher berikut
secara manual sebagai root di `/usr/local/sbin/projectlaboran-manage`. Launcher hanya
menerima release direct-child dengan nama SHA 40 hex dan operasi `migrate` atau
`collectstatic`. Environment dimuat oleh systemd untuk transient process, lalu
Python dijalankan sebagai user/group `admin`; tidak ada secret yang dicetak.

```bash
sudo tee /usr/local/sbin/projectlaboran-manage >/dev/null <<'LAUNCHER'
#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE_DIR=/home/admin/LabTif
RELEASES_DIR="$BASE_DIR/releases"
ENV_FILE=/etc/labhub/labhub.env
RUNTIME_USER=admin
RUNTIME_GROUP=admin

[[ $# -eq 2 ]] || { printf 'Usage: projectlaboran-manage <release> <operation>\n' >&2; exit 2; }
release=$1
operation=$2
[[ "$release" =~ ^/home/admin/LabTif/releases/[0-9a-fA-F]{40}$ ]] || exit 2
[[ "$(dirname -- "$release")" == "$RELEASES_DIR" ]] || exit 2
[[ -d "$release" && ! -L "$release" ]] || exit 2
[[ "$(readlink -f -- "$release")" == "$release" ]] || exit 2
[[ -f "$release/manage.py" && -x "$release/venv/bin/python" ]] || exit 2
[[ -f "$ENV_FILE" && ! -L "$ENV_FILE" ]] || exit 2
[[ "$(stat -c '%U:%G' "$ENV_FILE")" == root:root ]] || exit 2
[[ "$(stat -c '%a' "$ENV_FILE")" == 600 ]] || exit 2
[[ -x /usr/bin/systemd-run ]] || exit 2

case "$operation" in
    migrate) manage_args=(migrate --noinput) ;;
    collectstatic) manage_args=(collectstatic --noinput) ;;
    *) exit 2 ;;
esac

run_with_environment=(
    /usr/bin/systemd-run --quiet --wait --pipe --collect
    --uid="$RUNTIME_USER" --gid="$RUNTIME_GROUP"
    --working-directory="$release"
    --property="EnvironmentFile=$ENV_FILE"
)

"${run_with_environment[@]}" "$release/venv/bin/python" -c '
import os
from pathlib import Path

media = Path("/var/lib/labhub/media")
if os.environ.get("MEDIA_ROOT") != str(media) or not media.is_dir() or not os.access(media, os.W_OK):
    raise SystemExit("production media configuration is invalid")
'
exec "${run_with_environment[@]}" "$release/venv/bin/python" manage.py "${manage_args[@]}"
LAUNCHER
sudo chown root:root /usr/local/sbin/projectlaboran-manage
sudo chmod 0755 /usr/local/sbin/projectlaboran-manage
sudo bash -n /usr/local/sbin/projectlaboran-manage
sudo test "$(stat -c '%U:%G %a' /usr/local/sbin/projectlaboran-manage)" = 'root:root 755'
```

Runner hanya dapat mengeksekusi launcher; file root-owned ini tidak boleh berada di
workspace runner dan tidak dapat diubah oleh user `admin`.

## Sudo least privilege

Script memakai executable AlmaLinux `/usr/bin/systemctl`. Verifikasi path sebelum
memasang rule:

```bash
test "$(command -v systemctl)" = /usr/bin/systemctl
test "$(command -v systemd-run)" = /usr/bin/systemd-run
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
  'admin ALL=(root) NOPASSWD: /usr/local/sbin/projectlaboran-manage *' \
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
sudo -n -l /usr/local/sbin/projectlaboran-manage /home/admin/LabTif/releases/0000000000000000000000000000000000000000 migrate >/dev/null
sudo -n -l /usr/local/sbin/projectlaboran-manage /home/admin/LabTif/releases/0000000000000000000000000000000000000000 collectstatic >/dev/null
test "$(sudo -n /usr/bin/systemctl show projectlaboran-daphne --property=LoadState --value)" = loaded
```

Wildcard sudoers hanya memilih argumen untuk executable launcher root-owned; launcher
sendiri menolak jumlah argumen, path, dan operasi di luar allowlist. Jangan gunakan
`NOPASSWD: ALL`. Deploy melakukan seluruh preflight sudo sebelum publication,
migration, atau pergantian `current`.

## Konfigurasi systemd

Siapkan perubahan `/etc/systemd/system/projectlaboran-daphne.service` berikut,
tetapi jangan menjalankan `daemon-reload` atau restart unit berbasis `current` dulu:

```ini
[Service]
User=admin
Group=admin
UMask=0027
WorkingDirectory=/home/admin/LabTif/current
EnvironmentFile=/etc/labhub/labhub.env
ExecStart=/home/admin/LabTif/production-venv/bin/python -m daphne -b 127.0.0.1 -p 8000 project_laboran.asgi:application
```

Media cutover dan validasi checkout lama harus sudah berhasil sebelum tahap ini.
Verifikasi seluruh baseline, lalu lakukan `daemon-reload` saja. **Jangan stop atau
restart Daphne sebelum protected rollout pertama**:

```bash
test "$(readlink -f /home/admin/LabTif/current)" = /home/admin/LabTif/ProjectLaboran
test "$(readlink -f /home/admin/LabTif/production-venv)" = /home/admin/LabTif/ProjectLaboran/venv
sudo grep -q '^MEDIA_ROOT=/var/lib/labhub/media$' /etc/labhub/labhub.env
sudo test "$(stat -c '%U:%G %a' /etc/labhub/labhub.env)" = 'root:root 600'
test "$(readlink -f /home/admin/LabTif/ProjectLaboran/media)" = /var/lib/labhub/media
sudo /usr/bin/systemctl daemon-reload
sudo /usr/bin/systemctl is-active --quiet projectlaboran-daphne
curl --fail --max-time 5 -H 'Host: <production-hostname>' http://127.0.0.1/
```

`daemon-reload` hanya memuat definisi unit; proses Daphne lama tetap berjalan dengan
command dan environment lamanya. Symlink media membuat relative media path checkout
lama langsung menuju persistent storage tanpa restart. Karena `current` menunjuk
checkout lama dan `production-venv` resolve ke venv lamanya, restart tak terduga
setelah tahap ini tetap memiliki path valid. Restart yang direncanakan pertama hanya
dilakukan oleh deploy script setelah protected release diekstrak, venv selesai,
migration/collectstatic berhasil, dan `current` sudah berpindah atomik ke release itu.

## Isolasi self-hosted runner

Self-hosted runner deployment harus dedicated hanya untuk repository ini. Batasi
workflow deploy dengan GitHub Environment approval, protected branch/tag, dan akses
runner group. Jangan izinkan pull request fork, third-party workflow, atau job
arbitrary menjalankan command pada runner ini. Runner tidak menerima secret runtime
aplikasi di service environment; akses privileged-nya hanya sudoers systemctl dan
restricted launcher yang tercantum di atas.

## Model deployment dan rollback otomatis

Script memegang `flock` pada `/home/admin/LabTif/.deploy.lock`. Transaksi durable
ditulis atomik ke `/home/admin/LabTif/.deploy-transaction` dengan SHA, release path,
prior `current`, replacement backup, dan phase. File tidak pernah di-`source` atau
di-`eval`; parser menerima tepat enam field dan memvalidasi setiap path. Phase
`ready` ditulis sebelum switch, sehingga crash antara switch dan update phase tetap
terdeteksi dengan membandingkan `current` terhadap release transaksi.

Candidate dipublikasikan ke `/home/admin/LabTif/releases/<github-sha>` tanpa
mengubah runtime aktif. Candidate membuat venv final di `venv/` dan menginstal
requirements. Migration dan `collectstatic` hanya dijalankan lewat restricted
launcher; runner tidak menerima environment production. Hanya setelah langkah
pre-switch berhasil, symlink `current` diganti secara atomik.

Sesudah switch, script menjalankan `daemon-reload`, restart, `is-active`, lalu
mencoba `http://127.0.0.1:8000/` hingga 15 kali. Respons HTTP di bawah 500 dianggap
sehat; network failure atau status 500 ke atas memicu rollback. Error maupun signal
`TERM`, `INT`, dan `HUP` setelah switch mengembalikan `current` sebelumnya secara
atomik dan me-restart service. Signal sebelum switch tidak menyentuh service aktif.

Sisa `.deploy-*`, `.failed-*`, dan `.replaced-*` direkonsiliasi hanya saat lock
dipegang. `.replaced-*` hanya boleh dipulihkan/dihapus dengan provenance dari
transaction journal; orphan backup menghentikan deployment untuk inspeksi operator.
Startup dengan transaksi incomplete selalu memulihkan prior target secara atomik,
restart, `is-active`, dan health-check sebelum deployment baru boleh berjalan.

Setelah restart dan health berhasil, release mendapat marker `.deploy-success` yang
terikat ke SHA, transaksi ditandai `committed`, replacement backup dihapus secara
tervalidasi, lalu journal dihapus. Crash setelah health tetapi sebelum `committed`
di-rollback secara konservatif. Cleanup tidak pernah menghapus target `current`,
path di luar `releases`, atau release yang sedang dideploy. Setelah deployment sehat,
release aktif dan dua release inactive terbaru dipertahankan.

Rerun SHA yang sudah aktif menjadi no-op hanya jika tidak ada transaction incomplete
dan marker sukses cocok dengan SHA. Tanpa marker, script me-restart dan memverifikasi
release lebih dahulu sebelum membuat marker; service lama yang sekadar masih aktif
tidak cukup. SHA inactive diganti melalui staging dengan backup berprovenance.

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
    test ! -e "$BASE_DIR/.deploy-transaction" && test ! -L "$BASE_DIR/.deploy-transaction"
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
