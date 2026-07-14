from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('asleb', '0024_laporan_praktikum'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='absensiasleb',
            name='unique_absensi_asleb_per_modul',
        ),
    ]
