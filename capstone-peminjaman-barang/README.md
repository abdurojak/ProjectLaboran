# Peminjaman Barang Capstone

Web app ini dibuat untuk kebutuhan capstone peminjaman barang dengan backend ringan Node.js dan penyimpanan data di Google Sheet.

## Fitur utama

- Dashboard stok dan status peminjaman
- Form peminjaman barang
- Proses pengembalian barang
- Pencarian dan filter riwayat peminjaman
- Chat realtime dengan `Socket.IO`
- Room chat per `loan_id`, per barang, dan chat umum
- Sinkron realtime untuk stok, statistik, riwayat, pengembalian, dan feed aktivitas
- Mode demo lokal jika Google Sheet belum dikonfigurasi

## Struktur project

- `server.js` : server HTTP + REST API + integrasi Google Sheets API
- `public/` : frontend statis
- `scripts/build-sheet-template.mjs` : generator template spreadsheet
- `server.config.example.json` : contoh konfigurasi server
- `socket.io` : realtime chat antar user/admin

## Cara menjalankan

1. Copy `server.config.example.json` menjadi `server.config.json`
2. Isi `spreadsheetId` dengan ID spreadsheet Google Sheet kamu
3. Simpan file service account JSON dengan nama `google-service-account.json` di root project
4. Jalankan:

```powershell
node server.js
```

5. Buka `http://localhost:3000`

Kalau kamu bind server ke `0.0.0.0`, tetap buka dari browser dengan `http://localhost:3000` atau `http://127.0.0.1:3000`, bukan `http://0.0.0.0:3000`.

## Setup Google Sheet

1. Buat atau import spreadsheet template
2. Pastikan ada sheet bernama `Items`, `Loans`, dan `Chats`
3. Share spreadsheet ke email `client_email` dari service account sebagai `Editor`
4. Aktifkan Google Sheets API pada project Google Cloud service account kamu

## Format sheet yang dipakai

### Sheet `Items`

`item_id | item_name | category | stock_total | location | unit | notes`

### Sheet `Loans`

`loan_id | borrower_name | borrower_id | department | item_id | item_name | quantity | purpose | loan_date | due_date | status | request_notes | return_notes | returned_at | created_at`

### Sheet `Chats`

`chat_id | room_id | room_label | room_type | sender_name | sender_role | message | created_at`

## Catatan

- Kalau `server.config.json` atau `google-service-account.json` belum ada, aplikasi tetap hidup dalam mode demo.
- Jika sheet `Chats` belum ada, histori chat masih bisa jalan di mode demo lokal. Untuk penyimpanan permanen realtime, tambahkan sheet `Chats`.
- Semua tanggal diinput dalam format `YYYY-MM-DD`.
- Stok tersedia dihitung dari total stok dikurangi transaksi yang statusnya belum `Dikembalikan`.
