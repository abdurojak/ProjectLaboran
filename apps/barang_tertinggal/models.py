from datetime import date

from django.db import models
from django.urls import reverse


class BarangTertinggal(models.Model):
    STATUS_CHOICES = [
        ('tertinggal', 'Tertinggal'),
        ('hilang', 'Hilang'),
        ('diambil', 'Diambil'),
    ]

    kode_barang_tertinggal = models.CharField(max_length=15, unique=True, blank=True, editable=False)
    nama_barang = models.CharField(max_length=150)
    jenis_barang = models.CharField(max_length=100)
    jumlah_barang = models.PositiveIntegerField(default=1)
    foto = models.ImageField(upload_to='barang_tertinggal/', blank=True, null=True)
    lokasi_ditemukan = models.CharField(max_length=180, blank=True)
    tanggal_ditemukan = models.DateField()
    tanggal_diambil = models.DateField(blank=True, null=True)
    nama_pemilik = models.CharField(max_length=150, blank=True)
    nim_pemilik = models.CharField('NIM Pemilik', max_length=40, blank=True, db_index=True)
    pemilik = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='barang_tertinggal',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='tertinggal')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tanggal_ditemukan', '-dibuat_pada']
        verbose_name = 'Barang Tertinggal'
        verbose_name_plural = 'Barang Tertinggal'

    def save(self, *args, **kwargs):
        self._sync_pemilik_from_nim()
        super().save(*args, **kwargs)

        if not self.kode_barang_tertinggal:
            self.kode_barang_tertinggal = self.generate_kode_barang_tertinggal()
            super().save(update_fields=['kode_barang_tertinggal'])

    def _sync_pemilik_from_nim(self):
        self.nim_pemilik = (self.nim_pemilik or '').strip()
        if not self.nim_pemilik:
            self.pemilik = None
            return

        from apps.pengguna.models import Pengguna

        if self.pemilik_id and Pengguna.objects.filter(pk=self.pemilik_id, nim_nik=self.nim_pemilik).exists():
            return

        self.pemilik = Pengguna.objects.filter(nim_nik=self.nim_pemilik).first()

    @property
    def sudah_terhubung_akun(self):
        return bool(self.pemilik_id)

    def generate_kode_barang_tertinggal(self):
        tanggal_ditemukan = self.tanggal_ditemukan
        if isinstance(tanggal_ditemukan, str):
            tanggal_ditemukan = date.fromisoformat(tanggal_ditemukan)

        return f'BRT-{tanggal_ditemukan:%y%m%d}-{self.id:04d}'

    def get_absolute_url(self):
        return reverse('barang_tertinggal:detail', args=[self.pk])

    def __str__(self):
        return f'{self.kode_barang_tertinggal or "BRT"} - {self.nama_barang}'
