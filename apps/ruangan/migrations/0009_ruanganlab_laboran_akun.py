from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ruangan', '0008_separate_lab_head_and_laboran'),
        ('pengguna', '0019_limit_prodi_and_infer_from_nim'),
    ]

    operations = [
        migrations.AddField(
            model_name='ruanganlab',
            name='laboran_akun',
            field=models.ManyToManyField(
                blank=True, limit_choices_to={'role': 'laboran'},
                related_name='laboratorium_ditugaskan',
                to='pengguna.pengguna', verbose_name='Akun laboran penanggung jawab',
            ),
        ),
    ]
