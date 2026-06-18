from django.db import models


class Barang(models.Model):
    KONDISI_CHOICES = [
        ('baik', 'Baik'),
        ('rusak_ringan', 'Rusak Ringan'),
        ('rusak_berat', 'Rusak Berat'),
    ]

    nama = models.CharField(max_length=150)
    kode_barang = models.CharField(max_length=50, unique=True)
    jumlah = models.PositiveIntegerField(default=0)
    lokasi = models.CharField(max_length=150, blank=True)
    kondisi = models.CharField(max_length=20, choices=KONDISI_CHOICES, default='baik')
    keterangan = models.TextField(blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Barang'
        verbose_name_plural = 'Barang'

    def __str__(self):
        return f'{self.kode_barang} - {self.nama}'

# Create your models here.
