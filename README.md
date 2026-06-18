# Project Laboran

Project Laboran adalah aplikasi Django sederhana untuk membantu pencatatan inventaris laboratorium.

## Fitur awal

- Melihat daftar barang inventaris
- Menambah data barang
- Melihat detail barang
- Mengubah data barang
- Menghapus data barang

## Menjalankan proyek

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Setelah server berjalan, buka `http://127.0.0.1:8000/`.
