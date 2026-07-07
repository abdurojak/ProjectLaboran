from django.db import models


class RuanganLab(models.Model):
    WARNA_CHOICES = [
        ('teal', 'Teal'),
        ('amber', 'Amber'),
        ('blue', 'Biru'),
        ('emerald', 'Emerald'),
        ('violet', 'Violet'),
    ]

    nama = models.CharField(max_length=150)
    kode = models.CharField(max_length=30, unique=True)
    deskripsi = models.TextField(blank=True)
    kapasitas = models.PositiveSmallIntegerField(null=True, blank=True)
    warna = models.CharField(max_length=20, choices=WARNA_CHOICES, default='teal')
    aktif = models.BooleanField(default=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Ruangan Lab'
        verbose_name_plural = 'Ruangan Lab'

    def __str__(self):
        return f'{self.kode} - {self.nama}'


class FotoRuanganLab(models.Model):
    ruangan = models.ForeignKey(RuanganLab, on_delete=models.CASCADE, related_name='foto_lab')
    gambar = models.ImageField(upload_to='ruangan_lab/')
    judul = models.CharField(max_length=120, blank=True)
    urutan = models.PositiveSmallIntegerField(default=0)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['urutan', '-dibuat_pada']
        verbose_name = 'Foto Ruangan Lab'
        verbose_name_plural = 'Foto Ruangan Lab'

    def __str__(self):
        return self.judul or f'Foto {self.ruangan.nama}'


class GrupRuanganGabungan(models.Model):
    nama = models.CharField(max_length=150)
    ruangan = models.ManyToManyField(RuanganLab, related_name='grup_gabungan')
    deskripsi = models.TextField(blank=True)
    aktif = models.BooleanField(default=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nama']
        verbose_name = 'Grup Ruangan Gabungan'
        verbose_name_plural = 'Grup Ruangan Gabungan'

    def __str__(self):
        return self.nama

    def get_total_kapasitas(self):
        capacities = [
            ruangan.kapasitas
            for ruangan in self.ruangan.all()
            if ruangan.kapasitas is not None
        ]
        return sum(capacities) if capacities else None

    @classmethod
    def get_active_pair(cls, first_room, second_room):
        if not first_room or not second_room or first_room.pk == second_room.pk:
            return None
        return (
            cls.objects.filter(aktif=True, ruangan=first_room)
            .filter(ruangan=second_room)
            .distinct()
            .first()
        )

    @classmethod
    def get_combinable_room_ids_for(cls, room):
        if not room:
            return set()
        groups = cls.objects.filter(aktif=True, ruangan=room).prefetch_related('ruangan')
        return {
            grouped_room.pk
            for group in groups
            for grouped_room in group.ruangan.all()
            if grouped_room.pk != room.pk and grouped_room.aktif
        }
