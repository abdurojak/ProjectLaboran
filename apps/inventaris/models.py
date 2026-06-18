from django.db import models


class Lokasi(models.Model):
    kode_lokasi = models.CharField(max_length=8, unique=True, editable=False, blank=True)
    nama_lokasi = models.CharField(max_length=150)
    ukuran_lokasi = models.CharField(max_length=100, blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama_lokasi']
        verbose_name = 'Lokasi'
        verbose_name_plural = 'Lokasi'

    def __str__(self):
        return f'{self.kode_lokasi} - {self.nama_lokasi}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        kode_lokasi = f'LK{self.id:06d}'
        if self.kode_lokasi != kode_lokasi:
            self.kode_lokasi = kode_lokasi
            super().save(update_fields=['kode_lokasi'])


class Barang(models.Model):
    KONDISI_CHOICES = [
        ('baik', 'Baik'),
        ('rusak_ringan', 'Rusak Ringan'),
        ('rusak_berat', 'Rusak Berat'),
    ]

    nama = models.CharField(max_length=150)
    kode_barang = models.CharField(max_length=50, unique=True)
    jumlah = models.PositiveIntegerField(default=0)
    lokasi = models.ForeignKey(
        Lokasi,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='barang',
    )
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
