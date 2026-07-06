# Project Laboran

Project Laboran adalah aplikasi Django sederhana untuk membantu pencatatan inventaris laboratorium.

## Fitur awal

- Melihat daftar barang inventaris
- Menambah data barang
- Melihat detail barang
- Mengubah data barang
- Menghapus data barang

## Folder tambahan

- `capstone-peminjaman-barang/` berisi web app Node.js untuk demo peminjaman barang realtime dengan Socket.IO dan integrasi Google Sheet.

## Menjalankan proyek

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Setelah server berjalan, buka `http://127.0.0.1:8000/`.

## Aplikasi Android Absensi Asleb

Project Flutter tersedia di `mobile_absensi_asleb/`. API mobile berada di `/api/mobile/v1/` dan menggunakan JWT untuk akun dengan role Asisten Lab aktif. Panduan menjalankan Flutter dan build APK tersedia pada `mobile_absensi_asleb/README.md`.
