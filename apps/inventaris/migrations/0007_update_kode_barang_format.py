from django.db import migrations


def update_kode_barang_format(apps, schema_editor):
    Barang = apps.get_model('inventaris', 'Barang')

    barang_list = list(Barang.objects.order_by('id'))
    for barang in barang_list:
        barang.kode_barang = f'__BRG_MIG_{barang.id}'
        barang.save(update_fields=['kode_barang'])

    for index, barang in enumerate(barang_list, start=1):
        barang.kode_barang = f'BRG-{index:04d}'
        barang.save(update_fields=['kode_barang'])


def rollback_kode_barang_format(apps, schema_editor):
    Barang = apps.get_model('inventaris', 'Barang')

    barang_list = list(Barang.objects.order_by('id'))
    for barang in barang_list:
        barang.kode_barang = f'__LAB_MIG_{barang.id}'
        barang.save(update_fields=['kode_barang'])

    for index, barang in enumerate(barang_list, start=1):
        barang.kode_barang = f'LAB-{index:04d}'
        barang.save(update_fields=['kode_barang'])


class Migration(migrations.Migration):

    dependencies = [
        ('inventaris', '0006_inventarisbarang_barang_inventaris'),
    ]

    operations = [
        migrations.RunPython(update_kode_barang_format, rollback_kode_barang_format),
    ]
