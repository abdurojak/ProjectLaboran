from django.db import models


class PercakapanBantuan(models.Model):
    STATUS_CHOICES = [
        ('bot', 'Chat Bot'),
        ('admin', 'Menunggu Admin'),
        ('selesai', 'Selesai'),
    ]

    pengguna = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.CASCADE,
        related_name='percakapan_bantuan',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='bot')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-diperbarui_pada']
        verbose_name = 'Percakapan Bantuan'
        verbose_name_plural = 'Percakapan Bantuan'


class PesanBantuan(models.Model):
    PENGIRIM_CHOICES = [
        ('pengguna', 'Pengguna'),
        ('bot', 'Bot'),
        ('admin', 'Admin'),
    ]

    percakapan = models.ForeignKey(PercakapanBantuan, on_delete=models.CASCADE, related_name='pesan')
    pengirim = models.CharField(max_length=20, choices=PENGIRIM_CHOICES)
    isi = models.TextField(max_length=1000)
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['dibuat_pada', 'pk']
        verbose_name = 'Pesan Bantuan'
        verbose_name_plural = 'Pesan Bantuan'


class BugErrorLog(models.Model):
    KATEGORI_BUG = 'bug'
    KATEGORI_ERROR = 'error'
    KATEGORI_UI = 'ui'
    KATEGORI_DATA = 'data'
    KATEGORI_CHOICES = [
        (KATEGORI_BUG, 'Bug'),
        (KATEGORI_ERROR, 'Error'),
        (KATEGORI_UI, 'Tampilan/UI'),
        (KATEGORI_DATA, 'Data'),
    ]
    PRIORITAS_RENDAH = 'rendah'
    PRIORITAS_SEDANG = 'sedang'
    PRIORITAS_TINGGI = 'tinggi'
    PRIORITAS_KRITIS = 'kritis'
    PRIORITAS_CHOICES = [
        (PRIORITAS_RENDAH, 'Rendah'),
        (PRIORITAS_SEDANG, 'Sedang'),
        (PRIORITAS_TINGGI, 'Tinggi'),
        (PRIORITAS_KRITIS, 'Kritis'),
    ]
    STATUS_BARU = 'baru'
    STATUS_DIPROSES = 'diproses'
    STATUS_SELESAI = 'selesai'
    STATUS_CHOICES = [
        (STATUS_BARU, 'Baru'),
        (STATUS_DIPROSES, 'Diproses'),
        (STATUS_SELESAI, 'Selesai'),
    ]

    judul = models.CharField(max_length=180)
    kategori = models.CharField(max_length=20, choices=KATEGORI_CHOICES, default=KATEGORI_BUG)
    prioritas = models.CharField(max_length=20, choices=PRIORITAS_CHOICES, default=PRIORITAS_SEDANG)
    lokasi = models.CharField('Halaman/URL', max_length=500, blank=True)
    deskripsi = models.TextField()
    langkah_reproduksi = models.TextField(blank=True)
    ekspektasi = models.TextField(blank=True)
    hasil_aktual = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_BARU)
    catatan_admin = models.TextField(blank=True)
    dilaporkan_oleh = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.SET_NULL,
        related_name='bug_error_logs',
        blank=True,
        null=True,
    )
    ditangani_oleh = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.SET_NULL,
        related_name='bug_error_ditangani',
        blank=True,
        null=True,
    )
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-dibuat_pada']
        verbose_name = 'Bug & Error'
        verbose_name_plural = 'Bug & Error List'

    def __str__(self):
        return self.judul
