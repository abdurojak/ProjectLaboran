from datetime import date

from django.db import models
from django.urls import reverse


class BarangTertinggal(models.Model):
    STATUS_CHOICES = [
        ('tertinggal', 'Tertinggal'),
        ('diajukan', 'Diajukan'),
        ('diambil', 'Diambil'),
        ('rusak', 'Rusak'),
        ('hilang', 'Hilang'),
    ]

    kode_barang_tertinggal = models.CharField(max_length=15, unique=True, blank=True, editable=False)
    nama_barang = models.CharField(max_length=150)
    jenis_barang = models.CharField(max_length=100)
    jumlah_barang = models.PositiveIntegerField(default=1)
    foto = models.ImageField(upload_to='barang_tertinggal/', blank=True, null=True)
    tanggal_ditemukan = models.DateField()
    tanggal_diambil = models.DateField(blank=True, null=True)
    nama_pemilik = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='tertinggal')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tanggal_ditemukan', '-dibuat_pada']
        verbose_name = 'Barang Tertinggal'
        verbose_name_plural = 'Barang Tertinggal'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.kode_barang_tertinggal:
            self.kode_barang_tertinggal = self.generate_kode_barang_tertinggal()
            super().save(update_fields=['kode_barang_tertinggal'])

    def generate_kode_barang_tertinggal(self):
        tanggal_ditemukan = self.tanggal_ditemukan
        if isinstance(tanggal_ditemukan, str):
            tanggal_ditemukan = date.fromisoformat(tanggal_ditemukan)

        return f'BRT-{tanggal_ditemukan:%y%m%d}-{self.id:04d}'

    def get_absolute_url(self):
        return reverse('barang_tertinggal:detail', args=[self.pk])

    def __str__(self):
        return f'{self.kode_barang_tertinggal or "BRT"} - {self.nama_barang}'
