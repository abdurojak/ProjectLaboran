from datetime import date

from django.core.exceptions import ValidationError
from django.db import models

from apps.inventaris.models import Barang, PaketBarang


class PeminjamanAlat(models.Model):
    STATUS_CHOICES = [
        ('diajukan', 'Diajukan'),
        ('ditolak', 'Ditolak'),
        ('dipinjam', 'Dipinjam'),
        ('dikembalikan', 'Dikembalikan'),
        ('hilang', 'Hilang'),
        ('rusak', 'Rusak'),
        ('digantikan', 'Digantikan'),
    ]

    kode_pinjam = models.CharField(max_length=15, unique=True, blank=True, editable=False)
    barang = models.ForeignKey(Barang, on_delete=models.PROTECT, related_name='peminjaman')
    paket = models.ForeignKey(PaketBarang, on_delete=models.SET_NULL, related_name='peminjaman', blank=True, null=True)
    nama_peminjam = models.CharField(max_length=150)
    nim = models.CharField('NIM', max_length=30, blank=True)
    no_hp = models.CharField('No HP', max_length=30, blank=True)
    tanggal_pinjam = models.DateField()
    tanggal_kembali = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='diajukan')
    catatan = models.TextField(blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tanggal_pinjam', '-dibuat_pada']
        verbose_name = 'Peminjaman Alat'
        verbose_name_plural = 'Peminjaman Alat'

    def clean(self):
        if self.tanggal_kembali and self.tanggal_pinjam and self.tanggal_kembali < self.tanggal_pinjam:
            raise ValidationError({'tanggal_kembali': 'Tanggal kembali tidak boleh lebih awal dari tanggal pinjam.'})

        barang_sedang_dipinjam = False
        if self.barang_id:
            barang_sedang_dipinjam = self.barang.peminjaman.exclude(pk=self.pk).filter(
                status__in=['dipinjam', 'hilang', 'rusak'],
            ).exists()

        if self.barang_id and barang_sedang_dipinjam and self.status in ['diajukan', 'dipinjam']:
            raise ValidationError({'barang': 'Barang ini sedang dipinjam.'})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.kode_pinjam:
            self.kode_pinjam = self.generate_kode_pinjam()
            super().save(update_fields=['kode_pinjam'])

    def generate_kode_pinjam(self):
        tanggal_pinjam = self.tanggal_pinjam
        if isinstance(tanggal_pinjam, str):
            tanggal_pinjam = date.fromisoformat(tanggal_pinjam)

        return f'PJM-{tanggal_pinjam:%y%m%d}-{self.id:04d}'

    def __str__(self):
        return f'{self.kode_pinjam or "PJM"} - {self.nama_peminjam} - {self.barang.nama}'
