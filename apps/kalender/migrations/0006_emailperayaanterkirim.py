from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('kalender', '0005_kegiatankalender_ruangan'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailPerayaanTerkirim',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tanggal', models.DateField()),
                ('judul', models.CharField(max_length=200)),
                ('dikirim_pada', models.DateTimeField(auto_now_add=True)),
                ('pengguna', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='pengguna.pengguna')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('pengguna', 'tanggal', 'judul'), name='unique_email_perayaan_per_pengguna')],
            },
        ),
    ]
