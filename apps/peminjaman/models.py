from datetime import date

from django.core.exceptions import ValidationError
from django.db import models

from apps.inventaris.models import Barang, PaketBarang
from apps.pengguna.models import Pengguna


class PeminjamanTransaksi(models.Model):
    RISIKO_CHOICES = [
        ('normal', 'Normal'),
        ('rusak', 'Pernah rusak'),
        ('hilang', 'Pernah hilang'),
    ]

    kode_pinjam = models.CharField(max_length=15, unique=True, blank=True, editable=False)
    nama_peminjam = models.CharField(max_length=150)
    nim = models.CharField('NIM', max_length=30, blank=True)
    no_hp = models.CharField('No HP', max_length=30, blank=True)
    tanggal_pinjam = models.DateField()
    tanggal_kembali = models.DateField()
    tanggal_dikembalikan = models.DateField(blank=True, null=True)
    risiko = models.CharField(max_length=10, choices=RISIKO_CHOICES, default='normal')
    catatan = models.TextField(blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tanggal_pinjam', '-dibuat_pada']
        verbose_name = 'Transaksi Peminjaman'
        verbose_name_plural = 'Transaksi Peminjaman'

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

    @property
    def status_ringkas(self):
        statuses = list(self.detail.values_list('status', flat=True).distinct())
        if len(statuses) == 1:
            return statuses[0]
        return 'campuran'

    def __str__(self):
        return f'{self.kode_pinjam or "PJM"} - {self.nama_peminjam}'


class PengajuanPerpanjangan(models.Model):
    KONDISI_BARANG_CHOICES = [
        ('baik', 'Masih baik'),
        ('tidak_baik', 'Tidak baik / ada masalah'),
    ]
    STATUS_CHOICES = [
        ('diajukan', 'Menunggu persetujuan'),
        ('disetujui', 'Disetujui'),
        ('ditolak', 'Ditolak'),
    ]

    transaksi = models.ForeignKey(
        PeminjamanTransaksi,
        on_delete=models.CASCADE,
        related_name='pengajuan_perpanjangan',
    )
    diajukan_oleh = models.ForeignKey(
        Pengguna,
        on_delete=models.PROTECT,
        related_name='pengajuan_perpanjangan_peminjaman',
    )
    tanggal_kembali_sebelumnya = models.DateField()
    tanggal_kembali_diminta = models.DateField()
    tanggal_kembali_disetujui = models.DateField(blank=True, null=True)
    alasan = models.TextField()
    kondisi_barang = models.CharField(
        max_length=15,
        choices=KONDISI_BARANG_CHOICES,
        default='baik',
    )
    keterangan_kondisi = models.TextField(blank=True)
    pernyataan_jujur = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='diajukan')
    ditinjau_oleh = models.ForeignKey(
        Pengguna,
        on_delete=models.PROTECT,
        related_name='pengajuan_perpanjangan_ditinjau',
        blank=True,
        null=True,
    )
    catatan_peninjau = models.TextField(blank=True)
    ditinjau_pada = models.DateTimeField(blank=True, null=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-dibuat_pada']
        verbose_name = 'Pengajuan Perpanjangan Peminjaman'
        verbose_name_plural = 'Pengajuan Perpanjangan Peminjaman'

    def clean(self):
        errors = {}
        if (
            self.tanggal_kembali_diminta
            and self.tanggal_kembali_sebelumnya
            and self.tanggal_kembali_diminta <= self.tanggal_kembali_sebelumnya
        ):
            errors['tanggal_kembali_diminta'] = (
                'Tanggal perpanjangan harus setelah tanggal kembali saat ini.'
            )
        if self.kondisi_barang == 'tidak_baik' and len(self.keterangan_kondisi.strip()) < 10:
            errors['keterangan_kondisi'] = (
                'Jelaskan masalah atau kerusakan barang minimal 10 karakter.'
            )
        if not self.pernyataan_jujur:
            errors['pernyataan_jujur'] = (
                'Pernyataan kejujuran wajib disetujui sebelum mengajukan perpanjangan.'
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.transaksi.kode_pinjam} - {self.get_status_display()}'


class PenyesuaianSkorKredit(models.Model):
    pengguna = models.ForeignKey(
        Pengguna,
        on_delete=models.CASCADE,
        related_name='penyesuaian_skor_kredit',
    )
    skor_sebelum = models.PositiveSmallIntegerField()
    skor_baru = models.PositiveSmallIntegerField()
    nilai_penyesuaian = models.SmallIntegerField()
    tautan_konten = models.URLField(blank=True)
    catatan = models.CharField(max_length=300)
    diubah_oleh = models.ForeignKey(
        Pengguna,
        on_delete=models.PROTECT,
        related_name='perubahan_skor_kredit_dibuat',
    )
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dibuat_pada', '-pk']
        verbose_name = 'Penyesuaian Skor Kredit'
        verbose_name_plural = 'Penyesuaian Skor Kredit'

    def __str__(self):
        return f'{self.pengguna.nim_nik}: {self.skor_sebelum} menjadi {self.skor_baru}'


class PengingatPeminjaman(models.Model):
    JENIS_CHOICES = [
        ('jatuh_tempo', 'Jatuh tempo'),
        ('terlambat', 'Terlambat'),
    ]

    transaksi = models.ForeignKey(
        PeminjamanTransaksi,
        on_delete=models.CASCADE,
        related_name='pengingat_email',
    )
    tanggal = models.DateField()
    jenis = models.CharField(max_length=15, choices=JENIS_CHOICES)
    dikirim_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['transaksi', 'tanggal', 'jenis'],
                name='unique_pengingat_peminjaman_harian',
            ),
        ]
        verbose_name = 'Pengingat Peminjaman'
        verbose_name_plural = 'Pengingat Peminjaman'

    def __str__(self):
        return f'{self.transaksi.kode_pinjam} - {self.jenis} - {self.tanggal}'


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

    transaksi = models.ForeignKey(
        PeminjamanTransaksi,
        on_delete=models.CASCADE,
        related_name='detail',
        blank=True,
        null=True,
    )
    kode_pinjam = models.CharField(max_length=15, blank=True, editable=False)
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
        if not self.transaksi_id:
            self.transaksi = PeminjamanTransaksi.objects.create(
                kode_pinjam=self.kode_pinjam,
                nama_peminjam=self.nama_peminjam,
                nim=self.nim,
                no_hp=self.no_hp,
                tanggal_pinjam=self.tanggal_pinjam,
                tanggal_kembali=self.tanggal_kembali,
                catatan=self.catatan,
            )
            self.kode_pinjam = self.transaksi.kode_pinjam
        else:
            self.kode_pinjam = self.transaksi.kode_pinjam
        super().save(*args, **kwargs)

    def generate_kode_pinjam(self):
        tanggal_pinjam = self.tanggal_pinjam
        if isinstance(tanggal_pinjam, str):
            tanggal_pinjam = date.fromisoformat(tanggal_pinjam)

        return f'PJM-{tanggal_pinjam:%y%m%d}-{self.id:04d}'

    def __str__(self):
        return f'{self.kode_pinjam or "PJM"} - {self.nama_peminjam} - {self.barang.nama}'
