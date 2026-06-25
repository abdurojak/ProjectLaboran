from django.apps import apps
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

    @property
    def jumlah_periode_asleb(self):
        PendaftaranAsleb = apps.get_model('pendaftaran_asleb', 'PendaftaranAsleb')
        periode_count = PendaftaranAsleb.objects.filter(
            nim=self.nim,
            status__in=['diterima', 'digenerate'],
        ).count()
        return periode_count or 1

    @property
    def level_otomatis(self):
        return 'senior' if self.jumlah_periode_asleb >= 3 else 'junior'

    @property
    def level_otomatis_display(self):
        return 'Senior' if self.level_otomatis == 'senior' else 'Junior'


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
    METODE_TRANSFER_CHOICES = [
        ('rekening_bank', 'Rekening Bank'),
        ('dana', 'DANA'),
        ('ovo', 'OVO'),
    ]

    asleb = models.ForeignKey(Asleb, on_delete=models.CASCADE, related_name='honorarium')
    bulan = models.DateField(default=timezone.localdate)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='junior')
    jumlah_praktikum = models.PositiveSmallIntegerField(default=0)
    total_pertemuan = models.PositiveSmallIntegerField(default=0)
    jumlah = models.DecimalField(max_digits=12, decimal_places=2)
    metode_transfer = models.CharField(
        max_length=30,
        choices=METODE_TRANSFER_CHOICES,
        default='rekening_bank',
    )
    nomor_transfer = models.CharField('Nomor Rekening/E-Wallet', max_length=150, blank=True)
    nama_pemilik_transfer = models.CharField('Nama Pemilik Rekening/E-Wallet', max_length=150, blank=True)
    tanggal_transfer = models.DateField(blank=True, null=True)
    bukti_transfer = models.FileField('Bukti Screenshot Transfer', upload_to='honor_asleb/bukti_transfer/', blank=True)
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

    @property
    def tujuan_transfer(self):
        if not self.nomor_transfer:
            return '-'

        owner = f' a.n. {self.nama_pemilik_transfer}' if self.nama_pemilik_transfer else ''
        return f'{self.get_metode_transfer_display()} {self.nomor_transfer}{owner}'

    def save(self, *args, **kwargs):
        self.level = self.asleb.level_otomatis
        self.fill_transfer_from_registration()
        self.jumlah = self.total_honor
        super().save(*args, **kwargs)

    def fill_transfer_from_registration(self):
        if self.nomor_transfer and self.nama_pemilik_transfer:
            return

        PendaftaranAsleb = apps.get_model('pendaftaran_asleb', 'PendaftaranAsleb')
        registration = PendaftaranAsleb.objects.filter(
            nim=self.asleb.nim,
            status__in=['diterima', 'digenerate'],
        ).exclude(rekening='').order_by('-pk').first()

        if not registration:
            return

        if not self.nomor_transfer:
            self.metode_transfer = registration.metode_rekening
            self.nomor_transfer = registration.rekening

        if not self.nama_pemilik_transfer:
            self.nama_pemilik_transfer = registration.nama


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
    file_modul_hash = models.CharField(max_length=64, blank=True, db_index=True)
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
