from django.core.exceptions import ValidationError
from django.db import models


class KegiatanKalender(models.Model):
    judul = models.CharField(max_length=200)
    tanggal = models.DateField()
    waktu_mulai = models.TimeField()
    waktu_selesai = models.TimeField(blank=True, null=True)
    lokasi = models.CharField(max_length=150, blank=True)
    deskripsi = models.TextField(blank=True)
    tampilkan_notifikasi = models.BooleanField(default=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tanggal', 'waktu_mulai', 'judul']
        verbose_name = 'Kegiatan Kalender'
        verbose_name_plural = 'Kegiatan Kalender'

    def clean(self):
        if self.waktu_selesai and self.waktu_selesai < self.waktu_mulai:
            raise ValidationError({'waktu_selesai': 'Waktu selesai tidak boleh lebih awal dari waktu mulai.'})

    def __str__(self):
        return self.judul

