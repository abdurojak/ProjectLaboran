import uuid

from django.db import models


class MobileSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pengguna = models.ForeignKey(
        'pengguna.Pengguna',
        on_delete=models.CASCADE,
        related_name='sesi_mobile',
    )
    refresh_jti = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(blank=True, null=True, db_index=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dibuat_pada']
        indexes = [
            models.Index(
                fields=['pengguna', 'revoked_at', 'expires_at'],
                name='mobile_session_active_idx',
            ),
        ]
        verbose_name = 'Sesi Mobile'
        verbose_name_plural = 'Sesi Mobile'

    def __str__(self):
        return f'{self.pengguna} - {self.dibuat_pada:%d-%m-%Y %H:%M}'
