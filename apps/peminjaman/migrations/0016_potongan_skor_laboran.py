from django.db import migrations, models
import django.db.models.deletion


def preserve_existing_penalties(apps, schema_editor):
    Transaction = apps.get_model('peminjaman', 'PeminjamanTransaksi')
    Detail = apps.get_model('peminjaman', 'PeminjamanAlat')
    for transaction in Transaction.objects.iterator():
        details = Detail.objects.filter(transaksi_id=transaction.pk)
        statuses = set(details.values_list('status', flat=True))
        risk = 'hilang' if transaction.risiko == 'hilang' or 'hilang' in statuses else (
            'rusak' if transaction.risiko == 'rusak' or 'rusak' in statuses else 'normal'
        )
        if risk == 'normal':
            continue
        first_detail = details.order_by('pk').first()
        if first_detail:
            first_detail.potongan_skor = 40 if risk == 'hilang' else 20
            first_detail.save(update_fields=['potongan_skor'])


class Migration(migrations.Migration):
    dependencies = [
        ('peminjaman', '0015_peminjamanalat_is_capstone_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='peminjamanalat',
            name='potongan_skor',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='peminjamanalat',
            name='potongan_skor_oleh',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='potongan_skor_peminjaman', to='pengguna.pengguna',
            ),
        ),
        migrations.RunPython(preserve_existing_penalties, migrations.RunPython.noop),
    ]
