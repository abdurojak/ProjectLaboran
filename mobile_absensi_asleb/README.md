# LabHub Mobile

Aplikasi Flutter untuk Laboran, Asisten Lab aktif, dan Mahasiswa. Django tetap menjadi pusat autentikasi dan pembatasan fitur per role. Mahasiswa dapat melihat riwayat peminjamannya sendiri, sedangkan absensi hanya tersedia bagi Asisten Lab aktif.

## Endpoint API

Base URL produksi: `https://lab1.trisakti.ac.id/labhub/api/mobile/v1/`

| Method | Endpoint | Fungsi |
|---|---|---|
| POST | `auth/login/` | Login NIM/email dan password Asisten Lab |
| POST | `auth/refresh/` | Rotasi access dan refresh JWT |
| POST | `auth/logout/` | Logout API; aplikasi menghapus token terenkripsi |
| GET | `media/<path>/` | Mengambil gambar/file aplikasi dengan autentikasi JWT |
| GET | `profile/` | Profil dan mata kuliah Asisten Lab |
| GET | `mahasiswa/loans/` | Riwayat peminjaman milik Mahasiswa yang login |
| GET | `dashboard/` | Profil, jadwal hari ini, status absensi |
| GET | `schedules/` | Seluruh jadwal milik Asisten Lab |
| GET | `schedules/<id>/` | Detail dan ketersediaan absensi jadwal |
| POST | `attendance/check-in/` | Absensi masuk multipart |
| GET | `attendance/history/` | Riwayat foto dan video absensi |

Request `attendance/check-in/` menggunakan `multipart/form-data`: `jadwal_id`, `foto_absensi`, dan `video_absensi` (opsional).

## Menjalankan Backend

Di root Project Laboran:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Pastikan XAMPP/MySQL aktif. HP dan laptop harus berada di jaringan yang sama. Windows Firewall harus mengizinkan Python pada port `8000`.

Konfigurasi `.env` minimum:

```env
ALLOWED_HOSTS=localhost,127.0.0.1,lab1.trisakti.ac.id
PUBLIC_ACCESS_BASE_URL=https://lab1.trisakti.ac.id/labhub
```

## Menjalankan Flutter

```powershell
cd mobile_absensi_asleb
flutter pub get
flutter run --dart-define=API_BASE_URL=https://lab1.trisakti.ac.id/labhub/api/mobile/v1/
```

Untuk Android Emulator lokal gunakan `http://10.0.2.2:8000/api/mobile/v1/` jika server Django masih dijalankan manual di port 8000. Untuk HP fisik/production gunakan `https://lab1.trisakti.ac.id/labhub/api/mobile/v1/`.

## Build APK

Debug APK:

```powershell
flutter build apk --debug --dart-define=API_BASE_URL=https://lab1.trisakti.ac.id/labhub/api/mobile/v1/
```

Release APK:

```powershell
flutter build apk --release --dart-define=API_BASE_URL=https://lab1.trisakti.ac.id/labhub/api/mobile/v1/
```

Output berada di `build/app/outputs/flutter-apk/`. Build release menonaktifkan HTTP dan wajib memakai keystore resmi. Salin `android/key.properties.example` menjadi `android/key.properties`, isi kredensial keystore, lalu simpan file `.jks` pada lokasi `storeFile`. Kedua file rahasia tersebut sudah diabaikan Git.

## Catatan Keamanan

- JWT disimpan dengan `flutter_secure_storage`.
- Foto dan video hanya dapat dipilih melalui kamera pada UI aplikasi.
- Backend tetap memeriksa role aktif, jadwal, waktu, duplikasi, MIME, isi gambar, durasi MP4, dan ukuran file.
- Video bersifat opsional dan dibatasi maksimal 15 detik.
- APK debug mengizinkan HTTP LAN untuk pengembangan. APK release hanya menerima HTTPS agar password dan JWT tidak dikirim sebagai cleartext.
- APK release wajib ditandatangani keystore milik LabHub dan tidak lagi memakai debug key.
