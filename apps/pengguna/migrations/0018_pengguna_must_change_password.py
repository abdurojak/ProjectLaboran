from django.db import migrations, models


def require_existing_laboran_password_change(apps, schema_editor):
    Pengguna = apps.get_model('pengguna', 'Pengguna')
    Pengguna.objects.filter(role='laboran').update(must_change_password=True)


class Migration(migrations.Migration):
    dependencies = [
        ('pengguna', '0017_koneksipengguna'),
    ]

    operations = [
        migrations.AddField(
            model_name='pengguna',
            name='must_change_password',
            field=models.BooleanField(default=False, verbose_name='Wajib ganti password'),
        ),
        migrations.RunPython(require_existing_laboran_password_change, migrations.RunPython.noop),
    ]
