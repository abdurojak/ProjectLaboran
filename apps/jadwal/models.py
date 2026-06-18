from django.core.exceptions import ValidationError
from django.db import models


class JadwalPraktikum(models.Model):
    mata_praktikum = models.CharField(max_length=200)
    kelas = models.CharField(max_length=100)
    ruangan = models.CharField(max_length=150)
    pengampu = models.CharField(max_length=150)
    tanggal = models.DateField()
    waktu_mulai = models.TimeField()
    waktu_selesai = models.TimeField(blank=True, null=True)
    catatan = models.TextField(blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tanggal', 'waktu_mulai', 'mata_praktikum']
        verbose_name = 'Jadwal Praktikum'
        verbose_name_plural = 'Jadwal Praktikum'

    def clean(self):
        if self.waktu_selesai and self.waktu_selesai < self.waktu_mulai:
            raise ValidationError({'waktu_selesai': 'Waktu selesai tidak boleh lebih awal dari waktu mulai.'})

    def __str__(self):
        return f'{self.mata_praktikum} - {self.kelas}'

