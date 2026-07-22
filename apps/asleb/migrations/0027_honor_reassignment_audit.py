import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('asleb', '0026_normalize_mobile_attendance_status'),
        ('pendaftaran_asleb', '0018_aslab_replacement_workflow'),
        ('pengguna', '0016_rename_pengguna_sc_npsn_36628f_idx_pengguna_sc_npsn_495644_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='HonorReassignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bulan', models.DateField()),
                ('status', models.CharField(choices=[('held', 'Ditahan'), ('reassigned', 'Dialihkan'), ('correction_required', 'Perlu Koreksi')], max_length=24)),
                ('reason', models.TextField()),
                ('dibuat_pada', models.DateTimeField(auto_now_add=True)),
                ('acted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='honor_reassignments_acted', to='pengguna.pengguna')),
                ('final_asleb', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='incoming_honor_reassignments', to='asleb.asleb')),
                ('honor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reassignment_audits', to='asleb.honorasleb')),
                ('original_asleb', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='outgoing_honor_reassignments', to='asleb.asleb')),
                ('replacement', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='honor_reassignments', to='pendaftaran_asleb.aslabreplacement')),
            ],
            options={'ordering': ['bulan', 'pk']},
        ),
        migrations.AddConstraint(
            model_name='honorreassignment',
            constraint=models.UniqueConstraint(fields=('replacement', 'honor'), name='unique_replacement_honor_audit'),
        ),
        migrations.AddConstraint(
            model_name='honorreassignment',
            constraint=models.CheckConstraint(
                check=(models.Q(('final_asleb__isnull', False), ('status', 'reassigned')) | models.Q(('final_asleb__isnull', True), ('status__in', ['held', 'correction_required']))),
                name='honor_reassignment_final_guard',
            ),
        ),
    ]
