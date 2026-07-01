from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pengguna', '0012_linkedin_profile_fields')]

    operations = [
        migrations.AddField(
            model_name='pengguna',
            name='cover_image',
            field=models.ImageField(blank=True, null=True, upload_to='pengguna/covers/', verbose_name='Foto sampul'),
        ),
    ]
