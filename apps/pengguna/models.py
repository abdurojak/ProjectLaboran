from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import models
from django.urls import reverse


class Fakultas(models.Model):
    nama = models.CharField(max_length=120, unique=True)
    aktif = models.BooleanField(default=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Fakultas'
        verbose_name_plural = 'Fakultas'

    def __str__(self):
        return self.nama


class Prodi(models.Model):
    nama = models.CharField(max_length=120, unique=True)
    aktif = models.BooleanField(default=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Prodi'
        verbose_name_plural = 'Prodi'

    def __str__(self):
        return self.nama


class Pengguna(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('laboran', 'Laboran'),
        ('asisten_lab', 'Asisten Lab'),
        ('mahasiswa', 'Mahasiswa'),
    ]

    GENDER_CHOICES = [
        ('laki_laki', 'Laki-laki'),
        ('perempuan', 'Perempuan'),
    ]
    THEME_MODE_CHOICES = [
        ('light', 'Terang'),
        ('dark', 'Gelap'),
    ]
    BACKGROUND_MODE_CHOICES = [
        ('default', 'Default'),
        ('clean', 'Clean'),
        ('lab', 'Lab'),
        ('aurora', 'Aurora'),
        ('grid', 'Grid'),
        ('custom', 'Custom'),
    ]

    foto = models.ImageField(upload_to='pengguna/', blank=True, null=True)
    cover_image = models.ImageField('Foto sampul', upload_to='pengguna/covers/', blank=True, null=True)
    cv = models.FileField('CV', upload_to='pengguna/cv/', blank=True, null=True)
    kode_pengguna = models.CharField(max_length=10, unique=True, blank=True, editable=False)
    nama_pengguna = models.CharField(max_length=150)
    nim_nik = models.CharField('NIM/NIK', max_length=40, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    no_hp = models.CharField('No HP', max_length=30)
    alamat = models.TextField()
    fakultas = models.CharField(max_length=120)
    prodi = models.CharField(max_length=120)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='mahasiswa')
    is_verified = models.BooleanField('Terverifikasi', default=True)
    theme_mode = models.CharField(max_length=20, choices=THEME_MODE_CHOICES, default='light')
    background_mode = models.CharField(max_length=20, choices=BACKGROUND_MODE_CHOICES, default='default')
    background_image = models.ImageField(upload_to='pengguna/backgrounds/', blank=True, null=True)
    ringkasan_profesional = models.TextField('Tentang', blank=True)
    keahlian = models.TextField('Keahlian', blank=True, help_text='Pisahkan setiap keahlian dengan koma.')
    notifikasi_dibaca_pada = models.DateTimeField(blank=True, null=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama_pengguna']
        verbose_name = 'Pengguna'
        verbose_name_plural = 'Pengguna'

    def save(self, *args, **kwargs):
        if self.password and not self.password_is_hashed():
            self.password = make_password(self.password)

        super().save(*args, **kwargs)

        if not self.kode_pengguna:
            self.kode_pengguna = f'USR-{self.id:06d}'
            super().save(update_fields=['kode_pengguna'])

    def password_is_hashed(self):
        try:
            identify_hasher(self.password)
        except ValueError:
            return False

        return True

    def get_absolute_url(self):
        return reverse('pengguna:detail', args=[self.pk])

    def __str__(self):
        return f'{self.kode_pengguna or "USR"} - {self.nama_pengguna}'


class PengalamanPengguna(models.Model):
    KATEGORI_CHOICES = [
        ('pengalaman', 'Pengalaman'),
        ('pendidikan', 'Pendidikan'),
        ('organisasi', 'Organisasi'),
        ('proyek', 'Proyek'),
        ('sertifikasi', 'Lisensi & Sertifikasi'),
    ]

    pengguna = models.ForeignKey(Pengguna, on_delete=models.CASCADE, related_name='pengalaman')
    kategori = models.CharField(max_length=20, choices=KATEGORI_CHOICES, default='pengalaman')
    jabatan = models.CharField(max_length=150)
    organisasi = models.CharField(max_length=150)
    bidang_studi = models.CharField(max_length=150, blank=True)
    lokasi = models.CharField(max_length=150, blank=True)
    tanggal_mulai = models.DateField()
    tanggal_selesai = models.DateField(blank=True, null=True)
    masih_berjalan = models.BooleanField(default=False)
    deskripsi = models.TextField(blank=True)
    otomatis = models.BooleanField(default=False, editable=False)
    source_key = models.CharField(max_length=100, blank=True, unique=True, null=True, editable=False)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-masih_berjalan', '-tanggal_mulai', '-pk']
        verbose_name = 'Pengalaman Pengguna'
        verbose_name_plural = 'Pengalaman Pengguna'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.masih_berjalan:
            self.tanggal_selesai = None
        elif self.tanggal_selesai and self.tanggal_selesai < self.tanggal_mulai:
            raise ValidationError({'tanggal_selesai': 'Tanggal selesai tidak boleh lebih awal dari tanggal mulai.'})

    def __str__(self):
        return f'{self.jabatan} - {self.organisasi}'
