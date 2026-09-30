from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('pengguna', '0016_rename_pengguna_sc_npsn_36628f_idx_pengguna_sc_npsn_495644_idx_and_more')]

    operations = [
        migrations.CreateModel(
            name='KoneksiPengguna',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('mengikuti', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='koneksi_pengikut', to='pengguna.pengguna')),
                ('pengikut', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='koneksi_diikuti', to='pengguna.pengguna')),
            ],
            options={'ordering': ['-dibuat_pada']},
        ),
        migrations.AddConstraint(
            model_name='koneksipengguna',
            constraint=models.UniqueConstraint(fields=('pengikut', 'mengikuti'), name='unique_koneksi_pengguna'),
        ),
        migrations.AddConstraint(
            model_name='koneksipengguna',
            constraint=models.CheckConstraint(condition=~models.Q(pengikut=models.F('mengikuti')), name='koneksi_pengguna_bukan_diri_sendiri'),
        ),
    ]
