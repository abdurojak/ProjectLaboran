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

