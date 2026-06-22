from django.core.exceptions import ValidationError
from django.db import models


class JadwalPraktikum(models.Model):
    mata_kuliah = models.CharField('Matkul', max_length=200)
    kelas = models.CharField(max_length=100)
    letak_ruangan = models.CharField('Letak Ruangan', max_length=150)
    pengampu = models.CharField(max_length=150)
    tanggal = models.DateField()
    waktu_mulai = models.TimeField('Waktu Mulai')
    waktu_selesai = models.TimeField('Waktu Selesai', blank=True, null=True)
    catatan = models.TextField(blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tanggal', 'waktu_mulai', 'mata_kuliah']
        verbose_name = 'Jadwal Praktikum'
        verbose_name_plural = 'Jadwal Praktikum'

    def get_waktu_selesai_efektif(self):
        return self.waktu_selesai or self.waktu_mulai

    def clean(self):
        if self.waktu_selesai and self.waktu_selesai < self.waktu_mulai:
            raise ValidationError({'waktu_selesai': 'Waktu selesai tidak boleh lebih awal dari waktu mulai.'})

        if not self.tanggal or not self.letak_ruangan or not self.waktu_mulai:
            return

        waktu_selesai_baru = self.get_waktu_selesai_efektif()
        jadwal_di_ruangan = JadwalPraktikum.objects.filter(
            tanggal=self.tanggal,
            letak_ruangan__iexact=self.letak_ruangan.strip(),
        )

        if self.pk:
            jadwal_di_ruangan = jadwal_di_ruangan.exclude(pk=self.pk)

        for jadwal in jadwal_di_ruangan:
            waktu_selesai_lama = jadwal.get_waktu_selesai_efektif()
            if self.waktu_mulai < waktu_selesai_lama and waktu_selesai_baru > jadwal.waktu_mulai:
                raise ValidationError({
                    'letak_ruangan': (
                        'Ruangan ini sudah dipakai pada tanggal dan rentang waktu tersebut. '
                        'Silakan pilih waktu atau ruangan lain.'
                    )
                })

    def __str__(self):
        return f'{self.mata_kuliah} - {self.kelas}'

