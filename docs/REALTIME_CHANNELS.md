# Real-time LabHub

## Arsitektur

Daphne menjalankan aplikasi ASGI di `project_laboran.asgi`. Websocket dirutekan melalui
`project_laboran.routing` ke dua consumer:

- `/ws/bantuan/<percakapan_id>/` untuk chat bantuan.
- `/ws/notifikasi/` untuk notifikasi dan pembaruan UI real-time.

Consumer notifikasi membaca `pengguna_id` dari session Django. Koneksi tanpa session valid
ditutup dengan kode `4401`. Setiap koneksi hanya bergabung ke grup pribadi `user_<id>` dan
grup role `role_<role>`.

Notifikasi real-time tetap disimpan pada model `kalender.Notifikasi`. Websocket hanya menjadi
kanal pengiriman cepat dan tidak menggantikan validasi, transaksi, atau request HTTP.

## Event yang aktif

- Perubahan status pendaftaran Aslab.
- Pengajuan, persetujuan, penolakan, dan perubahan jadwal praktikum.
- Pembuatan dan pembaruan honor serta konfirmasi pembayaran.
- Absensi Asisten Lab yang berhasil disimpan.
- Badge notifikasi dan dashboard counter melalui refresh halaman ter-debounce.

CRUD biasa, profil, pengaturan, export, generate laporan, upload, login, dan logout tetap HTTP.

## Menjalankan development

```powershell
.\.venv\Scripts\python.exe -m daphne -b 0.0.0.0 -p 8000 project_laboran.asgi:application
```

Pada Linux:

```bash
./.venv/bin/python -m daphne -b 0.0.0.0 -p 8000 project_laboran.asgi:application
```

`InMemoryChannelLayer` cukup untuk satu proses development. Event tidak dapat dibagikan antar
beberapa proses Daphne atau antara worker terpisah.

## Redis untuk multi-process

Install paket berikut jika deployment memakai beberapa worker:

```bash
pip install channels-redis
```

Kemudian isi environment:

```env
CHANNEL_REDIS_URL=redis://127.0.0.1:6379/0
```

Jika variabel tersebut kosong, aplikasi otomatis kembali ke `InMemoryChannelLayer`.

## Testing browser

1. Jalankan Daphne, bukan WSGI server.
2. Login dan buka DevTools, tab Network, lalu filter `WS`.
3. Pastikan koneksi `/ws/notifikasi/` berstatus `101 Switching Protocols`.
4. Buka LabHub menggunakan dua browser/profile terpisah agar cookie session tidak sama.
5. Ubah status pendaftaran atau jadwal dari akun Laboran/Admin.
6. Pastikan akun penerima mendapat toast, badge berubah, dan halaman relevan diperbarui.
7. Matikan Daphne lalu buka halaman melalui server HTTP biasa untuk memastikan form tetap bekerja;
   client websocket akan mencoba kembali dengan jeda bertingkat tanpa loop error cepat.

Pengujian otomatis:

```bash
python manage.py test --settings=project_laboran.test_settings \
  apps.kalender.tests.NotificationRealtimeTests
```
