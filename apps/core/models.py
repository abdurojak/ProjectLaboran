from django.db import models


class PercakapanBantuan(models.Model):
    STATUS_CHOICES = [
        ('bot', 'Chat Bot'),
        ('admin', 'Menunggu Admin'),
        ('selesai', 'Selesai'),
    ]

    pengguna = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.CASCADE,
        related_name='percakapan_bantuan',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='bot')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-diperbarui_pada']
        verbose_name = 'Percakapan Bantuan'
        verbose_name_plural = 'Percakapan Bantuan'


class PesanBantuan(models.Model):
    PENGIRIM_CHOICES = [
        ('pengguna', 'Pengguna'),
        ('bot', 'Bot'),
        ('admin', 'Admin'),
    ]

    percakapan = models.ForeignKey(PercakapanBantuan, on_delete=models.CASCADE, related_name='pesan')
    pengirim = models.CharField(max_length=20, choices=PENGIRIM_CHOICES)
    isi = models.TextField(max_length=1000)
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['dibuat_pada', 'pk']
        verbose_name = 'Pesan Bantuan'
        verbose_name_plural = 'Pesan Bantuan'
