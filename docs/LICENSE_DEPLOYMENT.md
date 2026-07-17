# LabHub License Deployment

License Ed25519 versi 2 mengunci aplikasi ke fingerprint server. Validator hanya
memerlukan public key yang sudah tertanam di artifact; private key tidak pernah
berada di server production.

## Variabel production

Simpan hanya variabel berikut di `/etc/labhub/labhub.env`, bukan di Git:

```env
LABHUB_LICENSE_ENFORCED=True
LABHUB_LICENSE_KEY=<license-v2-dari-laptop-owner>
```

Override fingerprint bersifat opsional. Tambahkan hanya jika fingerprint yang
digunakan saat membuat license bukan nilai `/etc/machine-id`:

```env
LABHUB_LICENSE_FINGERPRINT=<fingerprint-yang-diset-owner>
```

Server tidak menyimpan verification key terpisah, signing key, shared secret,
atau private key. Saat development lokal, gunakan:

```env
LABHUB_LICENSE_ENFORCED=False
```

## Generate license di laptop owner

Ambil fingerprint target di AlmaLinux:

```bash
cat /etc/machine-id
```

Private key Ed25519 tetap hanya di laptop owner. Arahkan generator ke file private
key melalui `LABHUB_LICENSE_PRIVATE_KEY_FILE`; jangan unggah file tersebut ke Git,
CI artifact, atau server production.

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
memuat license production atau private key yang sebenarnya.

## Persiapan satu kali AlmaLinux

Jalankan perintah berikut satu kali. Folder deployment dan virtual environment
dimiliki oleh user `admin`:

```bash
sudo install -d -o admin -g admin -m 0755 /home/admin/LabTif
sudo install -d -o admin -g admin -m 0755 /home/admin/LabTif/releases
sudo -u admin python3 -m venv /home/admin/LabTif/production-venv
sudo chmod 0755 /home/admin/LabTif/production-venv
```

Pastikan ABI Python server sama dengan ABI yang dipakai workflow build, misalnya
`cp312-cp312`:

```bash
/home/admin/LabTif/production-venv/bin/python -c "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}')"
```

## Konfigurasi systemd

Pada `/etc/systemd/system/projectlaboran-daphne.service`, arahkan proses ke
symlink release aktif dan virtual environment production:

```ini
[Service]
User=admin
Group=admin
WorkingDirectory=/home/admin/LabTif/current
EnvironmentFile=/etc/labhub/labhub.env
ExecStart=/home/admin/LabTif/production-venv/bin/python -m daphne -b 0.0.0.0 -p 8000 project_laboran.asgi:application
```

Ganti license versi 1 lama di `/etc/labhub/labhub.env` dengan output versi 2.
Hapus baris `LABHUB_LICENSE_VERIFICATION_SECRET` dari file tersebut karena v2 tidak
memakai shared verification secret:

```bash
sudo sed -i '/^LABHUB_LICENSE_VERIFICATION_SECRET=/d' /etc/labhub/labhub.env
sudoedit /etc/labhub/labhub.env
sudo systemctl daemon-reload
```

Jangan restart service pada tahap ini. Artifact pertama harus berhasil membuat
`/home/admin/LabTif/current` terlebih dahulu; script deployment kemudian melakukan
restart dan pemeriksaan kesehatan.

## Model release dan rollback otomatis

Setiap artifact diekstrak ke direktori sementara, menjalankan instalasi dependency,
migration, dan `collectstatic`, lalu dipublikasikan sebagai
`/home/admin/LabTif/releases/<github-sha>`. Symlink
`/home/admin/LabTif/current` diganti secara atomik hanya setelah langkah sebelum
switch berhasil.

Deployment mengunci proses dengan `flock`, me-restart `projectlaboran-daphne`, dan
mencoba endpoint `http://127.0.0.1:8000/` beberapa kali. Respons HTTP di bawah 500
dianggap sehat; kegagalan koneksi atau status 500 ke atas memicu rollback. Jika
gagal setelah switch, script mengembalikan symlink lama dan me-restart service.
Jika belum ada release sebelumnya, symlink gagal dihapus dan service dihentikan
agar kondisi gagal terlihat jelas.

Setelah deployment sehat, release aktif dan dua release tidak aktif terbaru
dipertahankan. Kegagalan cleanup hanya menghasilkan warning dan tidak membatalkan
deployment yang sudah sehat.

Migration dijalankan sebelum symlink berpindah dan tidak di-rollback otomatis.
Gunakan migration yang backward-compatible dengan release sebelumnya. Rollback
aplikasi tidak boleh dianggap sebagai rollback schema atau data; perubahan database
yang tidak kompatibel memerlukan prosedur recovery terpisah yang sudah diuji.

## Rollback manual

Pilih SHA yang masih tersedia di `releases`, lalu ganti symlink secara atomik:

```bash
cd /home/admin/LabTif
find releases -mindepth 1 -maxdepth 1 -type d -printf '%TY-%Tm-%Td %TH:%TM %f\n' | sort -r
test -d /home/admin/LabTif/releases/<previous-github-sha>
ln -s /home/admin/LabTif/releases/<previous-github-sha> .current.rollback
mv -Tf .current.rollback current
sudo -n systemctl restart projectlaboran-daphne
sudo -n systemctl is-active --quiet projectlaboran-daphne
status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 5 http://127.0.0.1:8000/) && test "$status" -lt 500
readlink -f /home/admin/LabTif/current
```

Perintah ini hanya mengembalikan kode aplikasi. Evaluasi dampak migration terlebih
dahulu dan pulihkan database secara terpisah jika memang diperlukan.

## Catatan keamanan

Proteksi artifact bukan pengganti pembatasan akses server. Tetap gunakan permission
folder yang ketat dan batasi akses shell serta akses baca ke deployment production.
