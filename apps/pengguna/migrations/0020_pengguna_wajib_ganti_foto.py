from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pengguna', '0019_limit_prodi_and_infer_from_nim')]

    operations = [
        migrations.AddField(
            model_name='pengguna',
            name='wajib_ganti_foto',
            field=models.BooleanField(default=False),
        ),
    ]
