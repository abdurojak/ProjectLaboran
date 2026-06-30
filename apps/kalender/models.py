from django.core.exceptions import ValidationError
from django.db import models

from apps.pengguna.models import Pengguna


class KegiatanKalender(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('laboran', 'Laboran'),
        ('asisten_lab', 'Asisten Lab'),
        ('mahasiswa', 'Mahasiswa'),
    ]

    judul = models.CharField(max_length=200)
    tanggal = models.DateField()
    waktu_mulai = models.TimeField()
    waktu_selesai = models.TimeField(blank=True, null=True)
    lokasi = models.CharField(max_length=150, blank=True)
    deskripsi = models.TextField(blank=True)
    tampilkan_notifikasi = models.BooleanField(default=True)
    dibuat_oleh = models.ForeignKey(
        Pengguna,
        on_delete=models.SET_NULL,
        related_name='kegiatan_kalender',
        blank=True,
        null=True,
    )
    target_role = models.CharField(
        max_length=120,
        blank=True,
        help_text='Role yang bisa melihat kegiatan ini, dipisahkan koma.',
    )
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tanggal', 'waktu_mulai', 'judul']
        verbose_name = 'Kegiatan Kalender'
        verbose_name_plural = 'Kegiatan Kalender'

    def clean(self):
        if self.waktu_selesai and self.waktu_selesai < self.waktu_mulai:
            raise ValidationError({'waktu_selesai': 'Waktu selesai tidak boleh lebih awal dari waktu mulai.'})

    @property
    def target_role_list(self):
        return [role.strip() for role in self.target_role.split(',') if role.strip()]

    @property
    def target_role_display(self):
        role_labels = dict(self.ROLE_CHOICES)
        roles = self.target_role_list
        if not roles:
            return 'Pribadi'
        return ', '.join(role_labels.get(role, role) for role in roles)

    def visible_for(self, pengguna):
        if not pengguna:
            return True

        if pengguna.role in {'admin', 'laboran'}:
            return True

        if self.dibuat_oleh_id == pengguna.pk:
            return True

        if not self.dibuat_oleh_id and not self.target_role:
            return True

        return pengguna.role in self.target_role_list

    def __str__(self):
        return self.judul


class Notifikasi(models.Model):
    pengguna = models.ForeignKey(
        Pengguna,
        on_delete=models.CASCADE,
        related_name='notifikasi',
    )
    source_key = models.CharField(max_length=160)
    judul = models.CharField(max_length=220)
    deskripsi = models.TextField(blank=True)
    tanggal = models.DateField()
    waktu_label = models.CharField(max_length=80, blank=True)
    lokasi = models.CharField(max_length=180, blank=True)
    url = models.CharField(max_length=240, blank=True)
    badge = models.CharField(max_length=50, blank=True)
    icon = models.CharField(max_length=50, default='bell')
    icon_class = models.CharField(max_length=120, default='bg-slate-100 text-slate-600')
    source_updated_at = models.DateTimeField()
    dibaca_pada = models.DateTimeField(blank=True, null=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-source_updated_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['pengguna', 'source_key'], name='unique_notifikasi_per_pengguna_source'),
        ]
        verbose_name = 'Notifikasi'
        verbose_name_plural = 'Notifikasi'

    @property
    def is_read(self):
        return self.dibaca_pada is not None

    def __str__(self):
        return self.judul

