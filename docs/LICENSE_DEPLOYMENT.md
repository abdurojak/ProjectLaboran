# LabHub License Deployment

Fitur license ini mencegah hasil copy project langsung berjalan di server lain. License dikunci ke fingerprint server dan divalidasi saat Django startup jika `LABHUB_LICENSE_ENFORCED=True`.

## Variabel production

Simpan variabel ini di file environment server, misalnya `/etc/labhub/labhub.env`, bukan di Git.

```env
LABHUB_LICENSE_ENFORCED=True
LABHUB_LICENSE_KEY=isi-license-key
LABHUB_LICENSE_VERIFICATION_SECRET=isi-secret-yang-sama-dengan-generator
```

Saat development lokal, biarkan:

```env
LABHUB_LICENSE_ENFORCED=False
```

## Ambil fingerprint server AlmaLinux

Di server target:

```bash
cat /etc/machine-id
```

Nilai ini dipakai sebagai `--fingerprint` saat membuat license.

Jika perlu override manual, isi:

```env
LABHUB_LICENSE_FINGERPRINT=nilai-fingerprint-manual
```

## Generate license

Jalankan di komputer/admin yang kamu percaya. Jangan simpan `LABHUB_LICENSE_SIGNING_SECRET` di server yang tidak dipercaya.

PowerShell:

```powershell
$env:LABHUB_LICENSE_SIGNING_SECRET="secret-panjang-random"
python manage.py generate_labhub_license --customer "Lab FTI" --fingerprint "isi-machine-id-server" --expires-on 2030-01-31
```

Bash:

```bash
export LABHUB_LICENSE_SIGNING_SECRET="secret-panjang-random"
python manage.py generate_labhub_license --customer "Lab FTI" --fingerprint "isi-machine-id-server" --expires-on 2030-01-31
```

Output command adalah `LABHUB_LICENSE_KEY`.

## Catatan keamanan

Proteksi ini bukan pengganti pembatasan akses server. Tetap gunakan user Linux khusus, permission folder yang ketat, dan jangan berikan akses shell/source ke pihak yang tidak perlu.
