from datetime import time

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.ruangan.models import RuanganLab


class JadwalPraktikum(models.Model):
    ADDITIONAL_ROOM_CODE = 'LAB-RPL'
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
    ruangan_tambahan = models.ForeignKey(
        RuanganLab,
        on_delete=models.PROTECT,
        related_name='jadwal_praktikum_tambahan',
        blank=True,
        null=True,
    )
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

    def get_occupied_room_ids(self):
        room_ids = []
        if self.ruangan_id:
            room_ids.append(self.ruangan_id)
        if self.ruangan_tambahan_id:
            room_ids.append(self.ruangan_tambahan_id)
        return room_ids

    def get_display_ruangan_parts(self):
        parts = []
        if self.ruangan_id:
            parts.append(self.ruangan.nama)
        if self.ruangan_tambahan_id:
            parts.append(self.ruangan_tambahan.nama)
        return parts

    def get_display_ruangan_nama(self):
        parts = self.get_display_ruangan_parts()
        if not parts:
            return '-'
        return ' + '.join(parts)

    def get_display_ruangan_kapasitas(self):
        capacities = []
        if self.ruangan_id and self.ruangan.kapasitas is not None:
            capacities.append(self.ruangan.kapasitas)
        if self.ruangan_tambahan_id and self.ruangan_tambahan.kapasitas is not None:
            capacities.append(self.ruangan_tambahan.kapasitas)
        return sum(capacities) if capacities else None

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

        if self.ruangan_id and self.ruangan_tambahan_id:
            if self.ruangan_id == self.ruangan_tambahan_id:
                errors['ruangan_tambahan'] = 'Ruangan tambahan harus berbeda dari ruangan utama.'
            else:
                if self.ruangan_tambahan.kode != self.ADDITIONAL_ROOM_CODE:
                    errors['ruangan_tambahan'] = (
                        'Ruangan tambahan hanya boleh Lab Rekayasa Perangkat Lunak.'
                    )

        if errors:
            raise ValidationError(errors)

        if self.status != self.STATUS_DITERIMA:
            return

        if not self.hari or not self.ruangan_id or not self.waktu_mulai:
            return

        ruangan_ids = self.get_occupied_room_ids()
        jadwal_di_ruangan = JadwalPraktikum.objects.filter(
            hari=self.hari,
            status=self.STATUS_DITERIMA,
        ).filter(
            Q(ruangan_id__in=ruangan_ids) | Q(ruangan_tambahan_id__in=ruangan_ids)
        )

        if self.pk:
            jadwal_di_ruangan = jadwal_di_ruangan.exclude(pk=self.pk)

        for jadwal in jadwal_di_ruangan:
            waktu_selesai_lama = jadwal.get_waktu_selesai_efektif()
            if self.waktu_mulai < waktu_selesai_lama and waktu_selesai_baru > jadwal.waktu_mulai:
                raise ValidationError({
                    'ruangan': (
                        'Salah satu ruangan pada jadwal ini sudah dipakai pada hari dan rentang waktu tersebut. '
                        'Silakan pilih waktu atau ruangan lain.'
                    )
                })

    def __str__(self):
        return f'{self.mata_kuliah} - {self.kelas}'


class PermintaanPerubahanJadwal(models.Model):
    STATUS_CHOICES = [
        ('diajukan', 'Menunggu Persetujuan'),
        ('diterima', 'Disetujui'),
        ('ditolak', 'Ditolak'),
    ]

    jadwal = models.ForeignKey(JadwalPraktikum, on_delete=models.CASCADE, related_name='permintaan_perubahan')
    matkul = models.ForeignKey('pendaftaran_asleb.MataKuliahAsleb', on_delete=models.PROTECT)
    ruangan = models.ForeignKey(RuanganLab, on_delete=models.PROTECT, related_name='permintaan_jadwal_utama')
    ruangan_tambahan = models.ForeignKey(
        RuanganLab,
        on_delete=models.PROTECT,
        related_name='permintaan_jadwal_tambahan',
        blank=True,
        null=True,
    )
    hari = models.CharField(max_length=10, choices=JadwalPraktikum.HARI_CHOICES)
    waktu_mulai = models.TimeField()
    waktu_selesai = models.TimeField(blank=True, null=True)
    catatan = models.TextField(blank=True)
    diajukan_oleh = models.ForeignKey(
        'pengguna.Pengguna', on_delete=models.CASCADE, related_name='permintaan_perubahan_jadwal'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='diajukan')
    catatan_laboran = models.TextField(blank=True)
    diproses_oleh = models.ForeignKey(
        'pengguna.Pengguna', on_delete=models.SET_NULL, blank=True, null=True,
        related_name='permintaan_jadwal_diproses',
    )
    diproses_pada = models.DateTimeField(blank=True, null=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dibuat_pada']
        verbose_name = 'Permintaan Perubahan Jadwal'
        verbose_name_plural = 'Permintaan Perubahan Jadwal'

    def __str__(self):
        return f'Perubahan {self.jadwal} oleh {self.diajukan_oleh}'

