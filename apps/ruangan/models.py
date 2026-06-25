from django.db import models


class RuanganLab(models.Model):
    WARNA_CHOICES = [
        ('teal', 'Teal'),
        ('amber', 'Amber'),
        ('blue', 'Biru'),
        ('emerald', 'Emerald'),
        ('violet', 'Violet'),
    ]

    nama = models.CharField(max_length=150)
    kode = models.CharField(max_length=30, unique=True)
    deskripsi = models.TextField(blank=True)
    kapasitas = models.PositiveSmallIntegerField(null=True, blank=True)
    warna = models.CharField(max_length=20, choices=WARNA_CHOICES, default='teal')
    aktif = models.BooleanField(default=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Ruangan Lab'
        verbose_name_plural = 'Ruangan Lab'

    def __str__(self):
        return f'{self.kode} - {self.nama}'
