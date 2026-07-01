from django.db import models

from apps.pengguna.models import Pengguna


def default_items():
    return [
        {'nama': 'Kabel LAN', 'spesifikasi': 'UTP Cat 6 / RJ45', 'jumlah': '305 meter', 'keterangan': 'Praktikum Laboratorium Keamanan Sistem Informasi'},
        {'nama': 'Konektor RJ45', 'spesifikasi': 'Cat 6e NYK', 'jumlah': '10 Pack/500 pcs', 'keterangan': 'Praktikum Laboratorium Keamanan Sistem Informasi'},
        {'nama': 'PixEILink Network Cable Repair Tool Kit Set', 'spesifikasi': 'Set Paket Crimping', 'jumlah': '5 pcs', 'keterangan': 'Praktikum Laboratorium Keamanan Sistem Informasi'},
        {'nama': 'Baterai', 'spesifikasi': '9v', 'jumlah': '5 pcs', 'keterangan': 'Praktikum Laboratorium Keamanan Sistem Informasi'},
    ]


class SuratPengadaan(models.Model):
    nomor = models.CharField(max_length=120)
    tanggal = models.DateField()
    hal = models.CharField(max_length=200, default='Permohonan Pengadaan Kebutuhan Fasilitas Lab. Sistem dan Keamanan Informasi')
    lampiran = models.CharField(max_length=80, default='1 Berkas')
    tujuan_jabatan = models.CharField(max_length=150, default='Wakil Dekan II')
    tujuan_instansi = models.CharField(max_length=200, default='Fakultas Teknologi Industri\nUniversitas Trisakti Jakarta')
    isi = models.TextField()
    items = models.JSONField(default=default_items)
    nama_penandatangan = models.CharField(max_length=150, default='Ir. Gatot Budi Santoso, M.Kom')
    jabatan_penandatangan = models.CharField(max_length=150, default='Kepala Laboratorium')
    laboratorium = models.CharField(max_length=150, default='Sistem dan Keamanan Informasi')
    dibuat_oleh = models.ForeignKey(Pengguna, on_delete=models.PROTECT, related_name='surat_pengadaan')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tanggal', '-id']
        verbose_name = 'Surat Pengadaan'
        verbose_name_plural = 'Surat Pengadaan'

    def __str__(self):
        return f'{self.nomor} - {self.hal}'
