from django.db import models
from django.utils import timezone


class Asleb(models.Model):
    STATUS_CHOICES = [
        ('aktif', 'Aktif'),
        ('nonaktif', 'Nonaktif'),
    ]

    nama = models.CharField(max_length=150)
    nim = models.CharField('NIM', max_length=30, unique=True)
    no_hp = models.CharField('No HP', max_length=30)
    email = models.EmailField(blank=True)
    program_studi = models.CharField(max_length=120)
    matkul = models.CharField('Matkul', max_length=200, blank=True)
    semester = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aktif')
    tanggal_bergabung = models.DateField()
    catatan = models.TextField(blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Asleb'
        verbose_name_plural = 'Data Asleb'

    def __str__(self):
        return f'{self.nama} - {self.nim}'


class HonorAsleb(models.Model):
    LEVEL_CHOICES = [
        ('junior', 'Junior'),
        ('senior', 'Senior'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('diproses', 'Diproses'),
        ('dibayar', 'Dibayar'),
    ]

    asleb = models.ForeignKey(Asleb, on_delete=models.CASCADE, related_name='honorarium')
    bulan = models.DateField(default=timezone.localdate)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='junior')
    jumlah_praktikum = models.PositiveSmallIntegerField(default=0)
    total_pertemuan = models.PositiveSmallIntegerField(default=0)
    jumlah = models.DecimalField(max_digits=12, decimal_places=2)
    pic_transfer = models.CharField(max_length=120, blank=True)
    keterangan = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-bulan', 'asleb__nama']
        verbose_name = 'Honor Asleb'
        verbose_name_plural = 'Honor Asleb'

    def __str__(self):
        return f'{self.asleb.nama} - {self.bulan:%B %Y} - {self.jumlah}'

    @property
    def total_jam_terealisasi(self):
        return 7 * self.total_pertemuan

    @property
    def total_akhir(self):
        return min(self.total_jam_terealisasi, 60)

    @property
    def honor_per_jam(self):
        return 7000 if self.level == 'junior' else 8000

    @property
    def total_honor(self):
        return self.total_akhir * self.honor_per_jam

    @property
    def jumlah_rupiah(self):
        return f'Rp {self.jumlah:,.0f}'.replace(',', '.')

    @property
    def honor_per_jam_rupiah(self):
        return f'Rp {self.honor_per_jam:,.0f}'.replace(',', '.')

    def save(self, *args, **kwargs):
        self.jumlah = self.total_honor
        super().save(*args, **kwargs)


class PengaturanAbsensiAsleb(models.Model):
    dibuka = models.BooleanField(default=False)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pengaturan Absensi Asleb'
        verbose_name_plural = 'Pengaturan Absensi Asleb'

    @classmethod
    def get_solo(cls):
        pengaturan, _ = cls.objects.get_or_create(pk=1)
        return pengaturan

    def __str__(self):
        return 'Absensi Asleb Dibuka' if self.dibuka else 'Absensi Asleb Ditutup'


class AbsensiAsleb(models.Model):
    MODUL_CHOICES = [(number, f'Modul {number}') for number in range(1, 17)]

    asleb = models.ForeignKey(Asleb, on_delete=models.CASCADE, related_name='absensi')
    tanggal_praktikum = models.DateField(default=timezone.localdate)
    modul = models.PositiveSmallIntegerField(choices=MODUL_CHOICES)
    materi_praktikum = models.CharField(max_length=200, blank=True)
    pekerjaan = models.TextField(blank=True)
    file_modul = models.FileField('Upload Modul Praktikum', upload_to='absensi_asleb/modul/')
    bukti_video = models.FileField('Bukti Video Praktikum', upload_to='absensi_asleb/video/')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tanggal_praktikum', 'asleb__nama', 'modul']
        constraints = [
            models.UniqueConstraint(fields=['asleb', 'modul'], name='unique_absensi_asleb_per_modul'),
        ]
        verbose_name = 'Absensi Asleb'
        verbose_name_plural = 'Absensi Asleb'

    def __str__(self):
        return f'{self.asleb.nama} - Modul {self.modul}'
