from django.db import models


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
    tanggal_bergabung = models.DateField()
    catatan = models.TextField(blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Asleb'
        verbose_name_plural = 'Data Asleb'

    def __str__(self):
        return f'{self.nama} - {self.nim}'
