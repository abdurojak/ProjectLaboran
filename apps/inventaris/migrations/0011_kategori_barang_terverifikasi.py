from django.db import migrations, models


# Pemetaan berdasarkan barang yang benar-benar ada, bukan kemiripan nama.
KODE_PER_KATEGORI = {
    'sensor': '0002 0026 0027 0030 0036 0037 0038 0041 0045 0046 0052 0053 0058 0079 0086',
    'mikrokontroler': '0001 0023 0024 0032 0033 0055 0085',
    'modul': '0039 0040 0043 0047 0048 0049 0051 0054',
    'tampilan': '0003 0031 0042 0050 0059 0060 0061 0062 0063 0064 0065 0066 0067 0068 0069 0078 0080 0081',
    'daya': '0009 0028 0044 0070 0082',
    'motor': '0025 0057 0083',
    'kabel': '0016 0017 0035 0077 0084',
    'komputer': '0021',
    'elektronika': '0029 0056 0071 0072 0073 0074 0075 0076',
    'audio_visual': '0010 0011 0012 0013 0014 0018 0034',
    'perkakas': '0004 0005 0006 0007 0015 0019 0020',
}


def tetapkan_kategori_barang(apps, schema_editor):
    InventarisBarang = apps.get_model('inventaris', 'InventarisBarang')
    for kategori, nomor in KODE_PER_KATEGORI.items():
        kode = [f'LAB-{item}' for item in nomor.split()]
        InventarisBarang.objects.filter(kode_inventaris__in=kode).update(kategori=kategori)


class Migration(migrations.Migration):
    dependencies = [('inventaris', '0010_kategori_dan_foto_lokasi')]

    operations = [
        migrations.AlterField(
            model_name='inventarisbarang', name='kategori',
            field=models.CharField(
                choices=[
                    ('sensor', 'Sensor'), ('mikrokontroler', 'Board Mikro & SBC'),
                    ('modul', 'Modul & Antarmuka'), ('tampilan', 'Tampilan & Indikator'),
                    ('daya', 'Daya & Baterai'), ('motor', 'Motor & Aktuator'),
                    ('kabel', 'Kabel & Konektor'), ('komputer', 'Komputer & Periferal'),
                    ('jaringan', 'Jaringan'), ('elektronika', 'Komponen Elektronika'),
                    ('audio_visual', 'Audio, Video & XR'), ('perkakas', 'Perkakas & Alat Ukur'),
                    ('lainnya', 'Lainnya'),
                ], db_index=True, default='lainnya', max_length=20,
            ),
        ),
        migrations.RunPython(tetapkan_kategori_barang, migrations.RunPython.noop),
    ]
