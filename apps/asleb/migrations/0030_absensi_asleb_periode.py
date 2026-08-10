from datetime import date, timedelta

import django.db.models.deletion
from django.db import migrations, models


def _period_defaults(value):
    semester = 1 if value.month <= 6 else 2
    start_month = 1 if semester == 1 else 7
    end_month = 6 if semester == 1 else 12
    start = date(value.year, start_month, 1)
    end = date(value.year, end_month, 30 if end_month == 6 else 31)
    return semester, {
        'mulai': start,
        'selesai': end,
        'pendaftaran_mulai': start,
        'pendaftaran_selesai': start + timedelta(days=29),
    }


def backfill_attendance_period(apps, schema_editor):
    AbsensiAsleb = apps.get_model('asleb', 'AbsensiAsleb')
    PeriodeAsleb = apps.get_model('pendaftaran_asleb', 'PeriodeAsleb')
    alias = schema_editor.connection.alias

    for attendance in AbsensiAsleb.objects.using(alias).select_related('asleb').iterator():
        period = (
            PeriodeAsleb.objects.using(alias)
            .filter(mulai__lte=attendance.tanggal_praktikum, selesai__gte=attendance.tanggal_praktikum)
            .order_by('-tahun', '-semester')
            .first()
        )
        if period is None and attendance.asleb.periode_aktif_id:
            period = PeriodeAsleb.objects.using(alias).filter(
                pk=attendance.asleb.periode_aktif_id,
            ).first()
        if period is None:
            semester, defaults = _period_defaults(attendance.tanggal_praktikum)
            period, _ = PeriodeAsleb.objects.using(alias).get_or_create(
                tahun=attendance.tanggal_praktikum.year,
                semester=semester,
                defaults=defaults,
            )
        AbsensiAsleb.objects.using(alias).filter(pk=attendance.pk).update(periode_id=period.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('asleb', '0029_merge_20260722_1554'),
        ('pendaftaran_asleb', '0018_aslab_replacement_workflow'),
    ]

    operations = [
        migrations.AddField(
            model_name='absensiasleb',
            name='periode',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='absensi_asleb',
                to='pendaftaran_asleb.periodeasleb',
            ),
        ),
        migrations.RunPython(backfill_attendance_period, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='absensiasleb',
            name='unique_absensi_asleb_per_modul_praktikum',
        ),
        migrations.AlterField(
            model_name='absensiasleb',
            name='periode',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='absensi_asleb',
                to='pendaftaran_asleb.periodeasleb',
            ),
        ),
        migrations.AddConstraint(
            model_name='absensiasleb',
            constraint=models.UniqueConstraint(
                fields=('asleb', 'periode', 'modul_praktikum'),
                name='unique_absensi_asleb_periode_modul_praktikum',
            ),
        ),
    ]
