import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pendaftaran_asleb', '0019_koreksipengalamanasleb'),
        ('pengguna', '0016_rename_pengguna_sc_npsn_36628f_idx_pengguna_sc_npsn_495644_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='matakuliahasleb',
            name='maksimal_aslab',
            field=models.PositiveSmallIntegerField(default=2, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='Maksimal Aslab'),
        ),
        migrations.AddField(
            model_name='matakuliahasleb',
            name='kapasitas_diatur_oleh',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kapasitas_matkul_aslab_diatur', to='pengguna.pengguna'),
        ),
        migrations.AddField(
            model_name='matakuliahasleb',
            name='kapasitas_diatur_pada',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.RemoveConstraint(
            model_name='aslabslot',
            name='aslab_slot_number_1_or_2',
        ),
        migrations.AddConstraint(
            model_name='aslabslot',
            constraint=models.CheckConstraint(check=models.Q(('nomor__gte', 1), ('nomor__lte', 5)), name='aslab_slot_number_1_to_5'),
        ),
    ]
