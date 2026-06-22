from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import models
from django.urls import reverse


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

    foto = models.ImageField(upload_to='pengguna/', blank=True, null=True)
    kode_pengguna = models.CharField(max_length=10, unique=True, blank=True, editable=False)
    nama_pengguna = models.CharField(max_length=150)
    nim_nik = models.CharField('NIM/NIK', max_length=40, unique=True)
    email = models.EmailField()
    password = models.CharField(max_length=128)
    no_hp = models.CharField('No HP', max_length=30)
    alamat = models.TextField()
    fakultas = models.CharField(max_length=120)
    prodi = models.CharField(max_length=120)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='mahasiswa')
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
