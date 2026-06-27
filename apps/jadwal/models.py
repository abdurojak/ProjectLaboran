from datetime import time

from django.core.exceptions import ValidationError
from django.db import models

from apps.ruangan.models import RuanganLab


class JadwalPraktikum(models.Model):
    JAM_KERJA_MULAI = time(7, 30)
    JAM_KERJA_SELESAI = time(18, 0)
    STATUS_DIAJUKAN = 'diajukan'
    STATUS_DITERIMA = 'diterima'
    STATUS_DITOLAK = 'ditolak'
    HARI_CHOICES = [
        ('senin', 'Senin'),
        ('selasa', 'Selasa'),
        ('rabu', 'Rabu'),
        ('kamis', 'Kamis'),
        ('jumat', 'Jumat'),
        ('sabtu', 'Sabtu'),
    ]
    STATUS_CHOICES = [
        (STATUS_DIAJUKAN, 'Diajukan'),
        (STATUS_DITERIMA, 'Diterima'),
        (STATUS_DITOLAK, 'Ditolak'),
    ]

    mata_kuliah = models.CharField('Matkul', max_length=200)
    kelas = models.CharField(max_length=100)
    ruangan = models.ForeignKey(RuanganLab, on_delete=models.PROTECT, related_name='jadwal_praktikum')
    pengampu = models.CharField(max_length=150)
    hari = models.CharField(max_length=10, choices=HARI_CHOICES, default='senin')
    waktu_mulai = models.TimeField('Waktu Mulai')
    waktu_selesai = models.TimeField('Waktu Selesai', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DIAJUKAN)
    catatan = models.TextField(blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['hari', 'waktu_mulai', 'mata_kuliah']
        verbose_name = 'Jadwal Praktikum'
        verbose_name_plural = 'Jadwal Praktikum'

    def get_waktu_selesai_efektif(self):
        return self.waktu_selesai or self.waktu_mulai

    def clean(self):
        errors = {}

        if self.waktu_selesai and self.waktu_selesai <= self.waktu_mulai:
            errors['waktu_selesai'] = 'Waktu selesai harus lebih akhir dari waktu mulai.'

        if self.waktu_mulai:
            if self.waktu_mulai < self.JAM_KERJA_MULAI or self.waktu_mulai >= self.JAM_KERJA_SELESAI:
                errors['waktu_mulai'] = 'Waktu mulai harus berada dalam jam kerja 07:30-18:00.'

        waktu_selesai_baru = self.get_waktu_selesai_efektif()
        if waktu_selesai_baru and waktu_selesai_baru > self.JAM_KERJA_SELESAI:
            errors['waktu_selesai'] = 'Waktu selesai tidak boleh melewati jam kerja 18:00.'

        if errors:
            raise ValidationError(errors)

        if self.status != self.STATUS_DITERIMA:
            return

        if not self.hari or not self.ruangan_id or not self.waktu_mulai:
            return

        jadwal_di_ruangan = JadwalPraktikum.objects.filter(
            hari=self.hari,
            ruangan=self.ruangan,
            status=self.STATUS_DITERIMA,
        )

        if self.pk:
            jadwal_di_ruangan = jadwal_di_ruangan.exclude(pk=self.pk)

        for jadwal in jadwal_di_ruangan:
            waktu_selesai_lama = jadwal.get_waktu_selesai_efektif()
            if self.waktu_mulai < waktu_selesai_lama and waktu_selesai_baru > jadwal.waktu_mulai:
                raise ValidationError({
                    'ruangan': (
                        'Ruangan ini sudah dipakai pada hari dan rentang waktu tersebut. '
                        'Silakan pilih waktu atau ruangan lain.'
                    )
                })

    def __str__(self):
        return f'{self.mata_kuliah} - {self.kelas}'

