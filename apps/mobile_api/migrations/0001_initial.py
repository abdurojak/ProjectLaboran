# Generated manually for the server-managed mobile JWT session store.

import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('pengguna', '0016_rename_pengguna_sc_npsn_36628f_idx_pengguna_sc_npsn_495644_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='MobileSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('refresh_jti', models.CharField(max_length=64, unique=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('revoked_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('pengguna', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sesi_mobile', to='pengguna.pengguna')),
            ],
            options={
                'verbose_name': 'Sesi Mobile',
                'verbose_name_plural': 'Sesi Mobile',
                'ordering': ['-dibuat_pada'],
                'indexes': [models.Index(fields=['pengguna', 'revoked_at', 'expires_at'], name='mobile_session_active_idx')],
            },
        ),
    ]
