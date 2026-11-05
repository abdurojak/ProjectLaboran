from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('asleb', '0034_absensimasukasleb_modul_praktikum_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tugaslaporanpraktikum',
            name='lampiran_instruksi',
            field=models.FileField(blank=True, upload_to='instruksi_praktikum/%Y/%m/'),
        ),
        migrations.CreateModel(
            name='ProgresTugasPraktikum',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('todo', 'To Do'), ('in_progress', 'In Progress'), ('submitted', 'Submitted'), ('in_review', 'In Review'), ('graded', 'Graded')], default='todo', max_length=20)),
                ('diperbarui_pada', models.DateTimeField(auto_now=True)),
                ('peserta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progres_tugas', to='asleb.pesertapraktikum')),
                ('tugas', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progres_peserta', to='asleb.tugaslaporanpraktikum')),
            ],
            options={
                'verbose_name': 'Progres Tugas Praktikum',
                'verbose_name_plural': 'Progres Tugas Praktikum',
            },
        ),
        migrations.CreateModel(
            name='AktivitasTugasPraktikum',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('aksi', models.CharField(max_length=40)),
                ('keterangan', models.CharField(blank=True, max_length=250)),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('peserta', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='asleb.pesertapraktikum')),
                ('pengguna', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='pengguna.pengguna')),
                ('tugas', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aktivitas', to='asleb.tugaslaporanpraktikum')),
            ],
            options={
                'ordering': ['-dibuat_pada'],
                'verbose_name': 'Aktivitas Tugas Praktikum',
                'verbose_name_plural': 'Aktivitas Tugas Praktikum',
            },
        ),
        migrations.AddConstraint(
            model_name='progrestugaspraktikum',
            constraint=models.UniqueConstraint(fields=('tugas', 'peserta'), name='unique_progres_tugas_peserta'),
        ),
    ]
