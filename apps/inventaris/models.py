import re

from django.db.models import Sum
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
        kode_lokasi = f'LKS-{self.id:04d}'
        if self.kode_lokasi != kode_lokasi:
            self.kode_lokasi = kode_lokasi
            super().save(update_fields=['kode_lokasi'])


class InventarisBarang(models.Model):
    nama = models.CharField(max_length=150)
    kode_inventaris = models.CharField(max_length=50, unique=True, blank=True)
    jumlah = models.PositiveIntegerField(default=0)
    foto = models.ImageField(upload_to='barang/', blank=True, null=True)
    keterangan = models.TextField(blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Inventaris Barang'
        verbose_name_plural = 'Inventaris Barang'

    def __str__(self):
        return f'{self.kode_inventaris} - {self.nama}'

    @property
    def jumlah_dipinjam(self):
        if hasattr(self, 'jumlah_dipinjam_aktif'):
            return self.jumlah_dipinjam_aktif or 0

        return Barang.objects.filter(
            inventaris=self,
            peminjaman__status__in=['dipinjam', 'hilang', 'rusak'],
        ).aggregate(total=Sum('peminjaman__jumlah'))['total'] or 0

    @property
    def stok_tersedia(self):
        return max(self.jumlah - self.jumlah_dipinjam, 0)

    def save(self, *args, **kwargs):
        if not self.kode_inventaris:
            self.kode_inventaris = self.generate_kode_inventaris()
        super().save(*args, **kwargs)

    @classmethod
    def generate_kode_inventaris(cls):
        prefix = 'LAB'
        latest_code = (
            cls.objects.filter(kode_inventaris__startswith=f'{prefix}-')
            .order_by('-kode_inventaris')
            .values_list('kode_inventaris', flat=True)
            .first()
        )

        if not latest_code:
            return f'{prefix}-0001'

        match = re.search(r'(\d+)$', latest_code)
        next_number = int(match.group(1)) + 1 if match else cls.objects.count() + 1
        return f'{prefix}-{next_number:04d}'


class Barang(models.Model):
    KONDISI_CHOICES = [
        ('baik', 'Baik'),
        ('rusak_ringan', 'Rusak Ringan'),
        ('rusak_berat', 'Rusak Berat'),
    ]

    inventaris = models.ForeignKey(
        InventarisBarang,
        on_delete=models.CASCADE,
        related_name='detail_barang',
        null=True,
        blank=True,
    )
    nama = models.CharField(max_length=150)
    kode_barang = models.CharField(max_length=50, unique=True, blank=True)
    jumlah = models.PositiveIntegerField(default=0)
    lokasi = models.ForeignKey(
        Lokasi,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='barang',
    )
    kondisi = models.CharField(max_length=20, choices=KONDISI_CHOICES, default='baik')
    foto = models.ImageField(upload_to='barang/', blank=True, null=True)
    keterangan = models.TextField(blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Barang'
        verbose_name_plural = 'Barang'

    def __str__(self):
        nama = self.inventaris.nama if self.inventaris_id else self.kode_barang
        return f'{self.kode_barang} - {nama}'

    @property
    def jumlah_dipinjam(self):
        if hasattr(self, 'jumlah_dipinjam_aktif'):
            return self.jumlah_dipinjam_aktif or 0

        return self.peminjaman.filter(
            status__in=['dipinjam', 'hilang', 'rusak'],
        ).aggregate(total=Sum('jumlah'))['total'] or 0

    @property
    def stok_tersedia(self):
        if self.inventaris_id:
            return self.inventaris.stok_tersedia

        return max(self.jumlah - self.jumlah_dipinjam, 0)

    @property
    def sedang_dipinjam(self):
        return self.peminjaman.filter(status__in=['dipinjam', 'hilang', 'rusak']).exists()

    @property
    def status_pinjam(self):
        return 'Dipinjam' if self.sedang_dipinjam else 'Tersedia'

    def save(self, *args, **kwargs):
        if not self.kode_barang:
            self.kode_barang = self.generate_kode_barang()
        super().save(*args, **kwargs)

    @classmethod
    def generate_kode_barang(cls):
        prefix = 'BRG'
        latest_code = (
            cls.objects.filter(kode_barang__startswith=f'{prefix}-')
            .order_by('-kode_barang')
            .values_list('kode_barang', flat=True)
            .first()
        )

        if not latest_code:
            return f'{prefix}-0001'

        match = re.search(r'(\d+)$', latest_code)
        next_number = int(match.group(1)) + 1 if match else cls.objects.count() + 1
        return f'{prefix}-{next_number:04d}'
