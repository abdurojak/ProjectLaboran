from datetime import date, timedelta

from django.db import models
from django.utils import timezone


class MataKuliahAsleb(models.Model):
    MATKUL_CHOICES = [
        ('JK_IF01_IR_ADRIAN', 'Jaringan Komputer - Ir. Adrian Syamsul Gamar, MTI - TIF-01'),
        ('JK_TIF02_IR_GATOT', 'Jaringan Komputer - Ir. Gatot Budi Santoso, M.Kom - TIF-02'),
        ('MDI_TIF01_SYANDRA', 'Manajemen Data dan Informasi - Syandra Sari, M.Kom - TIF-01'),
        ('MDI_TIF02_ANUNG', 'Manajemen Data dan Informasi - Anung B. Attibowo, M.Kom - TIF-02'),
        ('MDI_BI01_AGUS', 'Manajemen Data dan Informasi - Agus Salim, S.T., MTI - BI-01'),
        ('MDI_BI02_SYANDRA', 'Manajemen Data dan Informasi - Syandra Sari, M.Kom - BI-02'),
        ('ERP_BI01_DINI', 'Enterprise Resource Planning - Ir. Dini Solihah, S.T., M.Kom - BI-01'),
        ('ERP_BI02_IR_TEDDY', 'Enterprise Resource Planning - Dr. Ir. Teddy Bickwanto, M.MSI - BI-02'),
        ('DW_BI01_IR_TEDDY', 'Data Warehouse - Dr. Ir. Teddy Bickwanto, M.MSI - BI-01'),
        ('DW_BI02_SYANDRA', 'Data Warehouse - Syandra Sari, M.Kom, MTI - BI-02'),
        ('SDA_TIF01_ABDUL', 'Struktur Data dan Algoritma - Abdul Roohman, M.Kom - TIF-01'),
        ('SDA_TIF02_ANUNG', 'Struktur Data dan Algoritma - Anung B. Attibowo, M.Kom - TIF-02'),
        ('SDA_BI01_ANUNG', 'Struktur Data dan Algoritma - Anung B. Attibowo, M.Kom - BI-01'),
        ('SDA_BI02_ABDUL', 'Struktur Data dan Algoritma - Abdul Roohman, M.Kom - BI-02'),
        ('PS_TIF01_DR_DEDY', 'Probabilitas dan Statistika - Dr. Dedy Sugiharto, S.Si., M.M., M.Kom - TIF-01'),
        ('PS_BI01_DRS_AYUDIN', 'Probabilitas dan Statistika - Drs. Ayfuddin, M.Si., Ph.D - BI-01'),
        ('PS_BI02_IR_JOKO', 'Probabilitas dan Statistika - Dr. Joko Putroto, M.MSI - BI-02'),
        ('PW_TIF02_DIAN', 'Pemrograman Web - Dian Pratiwi, S.T., MTI - TIF-02'),
        ('PW_TIF01_YUNIA', 'Pemrograman Web - Yunia Ningish, M.Kom - TIF-01'),
        ('PW_TIF01_DR_BINTI', 'Pemrograman Web - Dr. Binti Solihah, S.T., M.Kom - TIF-01'),
        ('PM_TIF01_RIFDAH', 'Pemrograman Mobile - Rifdah Amelia, M.Kom - TIF-01'),
        ('PM_TIF01_DIAN', 'Pemrograman Mobile - Dian Pratiwi, S.T., MTI - TIF-01'),
        ('PBO_TIF01_ABDUL', 'Pemrograman Berorientasi Objek - Abdul Roohman, M.Kom - TIF-01'),
        ('PBO_TIF02_DR_BINTI', 'Pemrograman Berorientasi Objek - Dr. Binti Solihah, S.T., M.Kom - TIF-02'),
        ('PBO_TIF02_DR_AHMAD', 'Pemrograman Berorientasi Objek - Dr Ahmad Zuhdi, S.Si., M.Kom - TIF-02'),
        ('AD_BI01_SYANDRA', 'Analitik Data - Syandra Sari, M.Kom - BI-01'),
        ('AD_BI02_DR_DEDY', 'Analitik Data - Dr. Dedy Sugiharto, S.Si., M.M., M.Kom - BI-02'),
        ('ML_BI01_ANUNG', 'Machine Learning - Anung B. Attibowo, M.Kom - BI-01'),
        ('KK_BI01_DR_BINTI', 'Keamanan Komputasi - Dr. Binti Solihah, S.T., M.Kom - BI-01'),
        ('KK_BI02_IR_WARDIANTO', 'Keamanan Komputasi - Ir. Wardianto, S.Si., M.Kom - BI-02'),
        ('KK_BI02_IR_ADRIAN', 'Keamanan Komputasi - Ir. Adrian Syamsul Gamar, MTI - BI-02'),
    ]

    kode = models.CharField(max_length=80, unique=True)
    nama = models.CharField(max_length=200)
    dosen = models.CharField(max_length=200)
    kelas = models.CharField(max_length=50)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ['nama', 'kelas', 'dosen']
        verbose_name = 'Mata Kuliah Aslab'
        verbose_name_plural = 'Mata Kuliah Aslab'

    def __str__(self):
        return f'{self.nama} - {self.dosen} - {self.kelas}'


class PengaturanPendaftaranAsleb(models.Model):
    dibuka = models.BooleanField(default=False)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pengaturan Pendaftaran Aslab'
        verbose_name_plural = 'Pengaturan Pendaftaran Aslab'

    @classmethod
    def get_solo(cls):
        pengaturan, _ = cls.objects.get_or_create(pk=1)
        return pengaturan

    def __str__(self):
        return 'Pendaftaran Aslab Dibuka' if self.dibuka else 'Pendaftaran Aslab Ditutup'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        today = timezone.localdate()
        period = PeriodeAsleb.get_for_date(today)
        if self.dibuka and not period.pendaftaran_dibuka:
            period.pendaftaran_mulai = today
            period.pendaftaran_selesai = min(period.selesai, today + timedelta(days=29))
            period.save(update_fields=['pendaftaran_mulai', 'pendaftaran_selesai', 'diperbarui_pada'])
        elif not self.dibuka and period.pendaftaran_dibuka:
            period.pendaftaran_selesai = today - timedelta(days=1)
            if period.pendaftaran_mulai > period.pendaftaran_selesai:
                period.pendaftaran_mulai = period.pendaftaran_selesai
            period.save(update_fields=['pendaftaran_mulai', 'pendaftaran_selesai', 'diperbarui_pada'])


class PeriodeAsleb(models.Model):
    SEMESTER_CHOICES = [(1, 'Januari - Juni'), (2, 'Juli - Desember')]

    tahun = models.PositiveSmallIntegerField()
    semester = models.PositiveSmallIntegerField(choices=SEMESTER_CHOICES)
    mulai = models.DateField()
    selesai = models.DateField()
    pendaftaran_mulai = models.DateField()
    pendaftaran_selesai = models.DateField()
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tahun', '-semester']
        constraints = [
            models.UniqueConstraint(fields=['tahun', 'semester'], name='unique_periode_asleb_per_semester'),
        ]
        verbose_name = 'Periode Aslab'
        verbose_name_plural = 'Periode Aslab'

    @property
    def nama(self):
        bulan = 'Januari - Juni' if self.semester == 1 else 'Juli - Desember'
        return f'{bulan} {self.tahun}'

    @property
    def pendaftaran_dibuka(self):
        today = timezone.localdate()
        return self.pendaftaran_mulai <= today <= self.pendaftaran_selesai

    @property
    def sedang_berjalan(self):
        today = timezone.localdate()
        return self.mulai <= today <= self.selesai

    @classmethod
    def get_for_date(cls, value=None):
        value = value or timezone.localdate()
        semester = 1 if value.month <= 6 else 2
        start_month = 1 if semester == 1 else 7
        end_month = 6 if semester == 1 else 12
        defaults = {
            'mulai': date(value.year, start_month, 1),
            'selesai': date(value.year, end_month, 30 if end_month == 6 else 31),
            'pendaftaran_mulai': date(value.year, start_month, 1),
            'pendaftaran_selesai': date(value.year, start_month, 1) + timedelta(days=29),
        }
        period, _ = cls.objects.get_or_create(tahun=value.year, semester=semester, defaults=defaults)
        return period

    def __str__(self):
        return self.nama


class PendaftaranAsleb(models.Model):
    STATUS_CHOICES = [
        ('diajukan', 'Diajukan'),
        ('diterima', 'Diterima'),
        ('ditolak', 'Ditolak'),
        ('digenerate', 'Masuk Data Aslab'),
    ]
    METODE_REKENING_CHOICES = [
        ('rekening_bank', 'Rekening Bank'),
        ('dana', 'DANA'),
        ('ovo', 'OVO'),
    ]
    NILAI_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('E', 'E'),
        ('tidak_terbaca', 'Tidak terbaca'),
    ]

    nama = models.CharField(max_length=150)
    nim = models.CharField('NIM', max_length=30)
    no_hp = models.CharField('No HP', max_length=30)
    email = models.EmailField(blank=True)
    program_studi = models.CharField(max_length=120)
    semester = models.PositiveSmallIntegerField()
    matkul = models.ForeignKey(MataKuliahAsleb, on_delete=models.PROTECT, related_name='pendaftaran')
    periode = models.ForeignKey(
        PeriodeAsleb,
        on_delete=models.PROTECT,
        related_name='pendaftaran',
        blank=True,
        null=True,
    )
    cv = models.FileField('CV', upload_to='pendaftaran_asleb/cv/', blank=True)
    transkrip = models.FileField('Transkrip', upload_to='pendaftaran_asleb/transkrip/', blank=True)
    tanda_tangan = models.ImageField('Tanda Tangan', upload_to='pendaftaran_asleb/tanda_tangan/', blank=True)
    metode_rekening = models.CharField(
        max_length=30,
        choices=METODE_REKENING_CHOICES,
        default='rekening_bank',
    )
    rekening = models.CharField(max_length=150, blank=True)
    nilai_transkrip = models.CharField(
        max_length=20,
        choices=NILAI_CHOICES,
        default='tidak_terbaca',
    )
    skor_nilai = models.PositiveSmallIntegerField(default=0)
    alasan = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='diajukan')
    tanggal_daftar = models.DateField(auto_now_add=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['matkul__nama', 'matkul__kelas', '-skor_nilai', 'dibuat_pada', 'nama']
        verbose_name = 'Pendaftaran Aslab'
        verbose_name_plural = 'Pendaftaran Aslab'

    def __str__(self):
        return f'{self.nama} - {self.matkul}'

    @staticmethod
    def grade_to_score(grade):
        return {
            'A': 3,
            'B': 2,
            'C': 1,
        }.get(grade, 0)
