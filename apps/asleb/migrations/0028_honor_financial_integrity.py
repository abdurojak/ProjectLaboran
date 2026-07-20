from django.db import migrations, models


def normalize_honor_records(apps, schema_editor):
    HonorAsleb = apps.get_model('asleb', 'HonorAsleb')
    grouped = {}
    for honor in HonorAsleb.objects.order_by('pk'):
        month = honor.bulan.replace(day=1)
        grouped.setdefault((honor.asleb_id, month), []).append(honor)

    for (_, month), records in grouped.items():
        def has_payment_evidence(item):
            return bool(item.tanggal_transfer and item.pic_transfer and item.bukti_transfer)

        records.sort(
            key=lambda item: (item.status == 'dibayar' and has_payment_evidence(item), item.pk),
            reverse=True,
        )
        primary, *duplicates = records
        notes = [item.keterangan.strip() for item in records if item.keterangan.strip()]

        primary.bulan = month
        if primary.status == 'dibayar' and not has_payment_evidence(primary):
            primary.status = 'diproses'
            notes.append('Status pembayaran lama dibuka kembali karena bukti transfer belum lengkap.')

        if primary.status != 'dibayar':
            primary.total_pertemuan = max(item.total_pertemuan for item in records)
            primary.jumlah_praktikum = max(item.jumlah_praktikum for item in records)
            primary.jumlah = max(item.jumlah for item in records)
            primary.biaya_admin = max(item.biaya_admin for item in records)

        if not primary.assigned_laboran_id:
            primary.assigned_laboran_id = next(
                (item.assigned_laboran_id for item in records if item.assigned_laboran_id),
                None,
            )
        primary.keterangan = ' | '.join(dict.fromkeys(notes))[:200]
        primary.save()

        if duplicates:
            HonorAsleb.objects.filter(pk__in=[item.pk for item in duplicates]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('asleb', '0027_alter_pengumpulanlaporanpraktikum_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='honorasleb',
            name='diarsipkan_pada',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(normalize_honor_records, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='honorasleb',
            constraint=models.UniqueConstraint(
                fields=('asleb', 'bulan'),
                name='unique_honor_asleb_per_bulan',
            ),
        ),
        migrations.AddConstraint(
            model_name='honorasleb',
            constraint=models.CheckConstraint(
                check=(
                    ~models.Q(status='dibayar')
                    | (
                        models.Q(tanggal_transfer__isnull=False)
                        & ~models.Q(pic_transfer='')
                        & ~models.Q(bukti_transfer='')
                    )
                ),
                name='paid_honor_requires_transfer_evidence',
            ),
        ),
    ]
