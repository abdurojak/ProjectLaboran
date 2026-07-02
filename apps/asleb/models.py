from django.apps import apps
from django.core.validators import MaxValueValidator, MinValueValidator
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
    periode_aktif = models.ForeignKey(
        'pendaftaran_asleb.PeriodeAsleb',
        on_delete=models.SET_NULL,
        related_name='asleb_aktif',
        blank=True,
        null=True,
    )
    tanggal_bergabung = models.DateField()
    catatan = models.TextField(blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Aslab'
        verbose_name_plural = 'Data Aslab'

    def __str__(self):
        return f'{self.nama} - {self.nim}'

    @property
    def jumlah_periode_asleb(self):
        PendaftaranAsleb = apps.get_model('pendaftaran_asleb', 'PendaftaranAsleb')
        periode_count = PendaftaranAsleb.objects.filter(
            nim=self.nim,
            status__in=['diterima', 'digenerate'],
            periode__isnull=False,
        ).values('periode_id').distinct().count()
        legacy_count = PendaftaranAsleb.objects.filter(
            nim=self.nim,
            status__in=['diterima', 'digenerate'],
            periode__isnull=True,
        ).count()
        return periode_count or legacy_count or 1

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
        ('bni', 'BNI'),
        ('bank_lain', 'Bank lain'),
        ('dana', 'DANA'),
        ('shopeepay', 'ShopeePay'),
        ('gopay', 'GoPay'),
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
        default='bni',
    )
    biaya_admin = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    nomor_transfer = models.CharField('Nomor Rekening/E-Wallet', max_length=150, blank=True)
    nama_pemilik_transfer = models.CharField('Nama Pemilik Rekening/E-Wallet', max_length=150, blank=True)
    tanggal_transfer = models.DateField(blank=True, null=True)
    bukti_transfer = models.FileField('Bukti Screenshot Transfer', upload_to='honor_asleb/bukti_transfer/', blank=True)
    assigned_laboran = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.SET_NULL,
        related_name='tugas_transfer_honor',
        blank=True,
        null=True,
        limit_choices_to={'role': 'laboran'},
        verbose_name='Laboran Penanggung Jawab TF',
    )
    pic_transfer = models.CharField(max_length=120, blank=True)
    keterangan = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-bulan', 'asleb__nama']
        verbose_name = 'Honor Aslab'
        verbose_name_plural = 'Honor Aslab'

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
    def honor_bersih(self):
        return max(self.total_honor - self.biaya_admin_transfer, 0)

    @property
    def biaya_admin_transfer(self):
        return {
            'bank_lain': 2500,
            'rekening_bank': 2500,
            'shopeepay': 1500,
            'gopay': 1500,
            'ovo': 1500,
        }.get(self.metode_transfer, 0)

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
        if not self.assigned_laboran_id:
            self.assigned_laboran = self.get_next_laboran_for_transfer()
        self.biaya_admin = self.biaya_admin_transfer
        self.jumlah = self.honor_bersih
        super().save(*args, **kwargs)

    def get_next_laboran_for_transfer(self):
        Pengguna = apps.get_model('pengguna', 'Pengguna')
        laboran_list = list(Pengguna.objects.filter(role='laboran', is_verified=True).order_by('nama_pengguna', 'pk'))
        if not laboran_list:
            return None

        bulan_awal = self.bulan.replace(day=1)
        load_by_laboran = {
            item['assigned_laboran_id']: item['total']
            for item in HonorAsleb.objects.filter(
                bulan__year=bulan_awal.year,
                bulan__month=bulan_awal.month,
                assigned_laboran__isnull=False,
            )
            .exclude(pk=self.pk)
            .values('assigned_laboran_id')
            .annotate(total=models.Count('id'))
        }
        return min(laboran_list, key=lambda laboran: (load_by_laboran.get(laboran.pk, 0), laboran.nama_pengguna, laboran.pk))

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


def default_surat_honor_expires_at():
    today = timezone.localdate()
    try:
        return today.replace(year=today.year + 5)
    except ValueError:
        return today.replace(month=2, day=28, year=today.year + 5)


class SuratHonorAsleb(models.Model):
    bulan = models.DateField()
    nomor_surat = models.CharField(max_length=120)
    tanggal_surat = models.DateField(default=timezone.localdate)
    perihal = models.CharField(max_length=200, default='Laporan Kegiatan Asisten Laboratorium Jurusan Teknik Informatika')
    file_pdf = models.FileField(upload_to='surat_honor_asleb/')
    dibuat_oleh = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.SET_NULL,
        related_name='surat_honor_dibuat',
        blank=True,
        null=True,
    )
    total_honor = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    jumlah_asleb = models.PositiveIntegerField(default=0)
    expires_at = models.DateField(default=default_surat_honor_expires_at)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-bulan', '-dibuat_pada']
        verbose_name = 'Surat Honor Aslab'
        verbose_name_plural = 'Arsip Surat Honor Aslab'

    def __str__(self):
        return f'{self.nomor_surat} - {self.bulan:%B %Y}'

    @property
    def bulan_label(self):
        bulan_names = [
            '',
            'Januari',
            'Februari',
            'Maret',
            'April',
            'Mei',
            'Juni',
            'Juli',
            'Agustus',
            'September',
            'Oktober',
            'November',
            'Desember',
        ]
        return f'{bulan_names[self.bulan.month]} {self.bulan.year}'

    @property
    def total_honor_rupiah(self):
        return f'Rp {self.total_honor:,.0f}'.replace(',', '.')


class PengaturanAbsensiAsleb(models.Model):
    dibuka = models.BooleanField(default=False)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pengaturan Absensi Aslab'
        verbose_name_plural = 'Pengaturan Absensi Aslab'

    @classmethod
    def get_solo(cls):
        pengaturan, _ = cls.objects.get_or_create(pk=1)
        return pengaturan

    def __str__(self):
        return 'Absensi Aslab Dibuka' if self.dibuka else 'Absensi Aslab Ditutup'


class ModulPraktikum(models.Model):
    matkul = models.ForeignKey(
        'pendaftaran_asleb.MataKuliahAsleb',
        on_delete=models.PROTECT,
        related_name='modul_praktikum',
    )
    nomor = models.PositiveSmallIntegerField()
    judul = models.CharField(max_length=200)
    file = models.FileField(upload_to='modul_praktikum/')
    diunggah_oleh = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='modul_praktikum_diunggah',
    )
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['matkul__nama', 'matkul__kelas', 'nomor']
        constraints = [
            models.UniqueConstraint(fields=['matkul', 'nomor'], name='unique_nomor_modul_per_matkul'),
        ]
        verbose_name = 'Modul Praktikum'
        verbose_name_plural = 'Modul Praktikum'

    def __str__(self):
        return f'Modul {self.nomor} - {self.judul}'


class AbsensiAsleb(models.Model):
    MODUL_CHOICES = [(number, f'Modul {number}') for number in range(1, 17)]

    asleb = models.ForeignKey(Asleb, on_delete=models.CASCADE, related_name='absensi')
    jadwal = models.ForeignKey(
        'jadwal.JadwalPraktikum',
        on_delete=models.PROTECT,
        related_name='absensi_asleb',
        blank=True,
        null=True,
    )
    modul_praktikum = models.ForeignKey(
        ModulPraktikum,
        on_delete=models.PROTECT,
        related_name='absensi',
        blank=True,
        null=True,
    )
    tanggal_praktikum = models.DateField(default=timezone.localdate)
    modul = models.PositiveSmallIntegerField(choices=MODUL_CHOICES)
    materi_praktikum = models.CharField(max_length=200, blank=True)
    pekerjaan = models.TextField(blank=True)
    file_modul = models.FileField('Upload Modul Praktikum', upload_to='absensi_asleb/modul/')
    file_modul_hash = models.CharField(max_length=64, blank=True, db_index=True)
    bukti_foto = models.ImageField('Bukti Foto Praktikum', upload_to='absensi_asleb/foto/', blank=True)
    bukti_video = models.FileField('Bukti Video Praktikum', upload_to='absensi_asleb/video/')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    jarak_lokasi_meter = models.PositiveIntegerField(blank=True, null=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tanggal_praktikum', 'asleb__nama', 'modul']
        constraints = [
            models.UniqueConstraint(fields=['asleb', 'modul'], name='unique_absensi_asleb_per_modul'),
            models.UniqueConstraint(
                fields=['asleb', 'modul_praktikum'],
                name='unique_absensi_asleb_per_modul_praktikum',
            ),
        ]
        verbose_name = 'Absensi Aslab'
        verbose_name_plural = 'Absensi Aslab'

    def __str__(self):
        return f'{self.asleb.nama} - Modul {self.modul}'


class PesertaPraktikum(models.Model):
    matkul = models.ForeignKey(
        'pendaftaran_asleb.MataKuliahAsleb',
        on_delete=models.PROTECT,
        related_name='peserta_praktikum',
    )
    pengguna = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='kelas_praktikum',
    )
    nim = models.CharField('NIM', max_length=40)
    nama = models.CharField(max_length=150)
    aktif = models.BooleanField(default=True)
    dibuat_oleh = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='peserta_praktikum_dibuat',
    )
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['matkul__nama', 'matkul__kelas', 'nama']
        constraints = [
            models.UniqueConstraint(fields=['matkul', 'nim'], name='unique_peserta_per_matkul'),
        ]
        verbose_name = 'Peserta Praktikum'
        verbose_name_plural = 'Peserta Praktikum'

    def __str__(self):
        return f'{self.nim} - {self.nama} ({self.matkul})'


class HasilPraktikumMahasiswa(models.Model):
    STATUS_CHOICES = [
        ('hadir', 'Hadir'),
        ('izin', 'Izin'),
        ('sakit', 'Sakit'),
        ('alpa', 'Alpa'),
    ]

    peserta = models.ForeignKey(PesertaPraktikum, on_delete=models.PROTECT, related_name='hasil_praktikum')
    modul = models.ForeignKey(ModulPraktikum, on_delete=models.PROTECT, related_name='hasil_mahasiswa')
    tanggal_praktikum = models.DateField(default=timezone.localdate)
    status_absensi = models.CharField(max_length=12, choices=STATUS_CHOICES, default='hadir')
    nilai = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    catatan = models.CharField(max_length=250, blank=True)
    dicatat_oleh = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='hasil_praktikum_dicatat',
    )
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['modul__nomor', 'peserta__nama']
        constraints = [
            models.UniqueConstraint(fields=['peserta', 'modul'], name='unique_hasil_peserta_per_modul'),
        ]
        verbose_name = 'Nilai dan Absensi Mahasiswa'
        verbose_name_plural = 'Nilai dan Absensi Mahasiswa'

    def clean(self):
        super().clean()
        if self.peserta_id and self.modul_id and self.peserta.matkul_id != self.modul.matkul_id:
            from django.core.exceptions import ValidationError
            raise ValidationError({'modul': 'Modul harus berasal dari mata kuliah peserta.'})

    def __str__(self):
        return f'{self.peserta.nama} - {self.modul} - {self.get_status_absensi_display()}'


class PengingatAbsensiAsleb(models.Model):
    asleb = models.ForeignKey(Asleb, on_delete=models.CASCADE, related_name='pengingat_absensi')
    jadwal = models.ForeignKey('jadwal.JadwalPraktikum', on_delete=models.CASCADE, related_name='pengingat_absensi_asleb')
    tanggal = models.DateField()
    tahap = models.PositiveSmallIntegerField()
    dikirim_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['tanggal', 'jadwal__waktu_mulai', 'tahap']
        constraints = [
            models.UniqueConstraint(
                fields=['asleb', 'jadwal', 'tanggal', 'tahap'],
                name='unique_pengingat_absensi_asleb',
            ),
        ]
        verbose_name = 'Pengingat Absensi Aslab'
        verbose_name_plural = 'Pengingat Absensi Aslab'
