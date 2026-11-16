from django.db import migrations, models


def kelompokkan_barang(apps, schema_editor):
    InventarisBarang = apps.get_model('inventaris', 'InventarisBarang')
    rules = [
        ('sensor', ('sensor', 'dht', 'ultrasonik', 'pir ', 'rfid', 'gy-')),
        ('mikrokontroler', ('arduino', 'esp32', 'esp8266', 'raspberry', 'micro:bit', 'nodemcu', 'mikrokontroler')),
        ('jaringan', ('router', 'switch', 'access point', 'ethernet', 'lan tester', 'mikrotik', 'modem')),
        ('audio_visual', ('kamera', 'camera', 'tripod', 'proyektor', 'projector', 'mikrofon', 'microphone', 'speaker')),
        ('elektronika', ('osiloskop', 'oscilloscope', 'multimeter', 'breadboard', 'solder', 'power supply', 'resistor', 'kapasitor', 'relay')),
        ('komputer', ('laptop', 'komputer', 'monitor', 'keyboard', 'mouse', 'printer', 'scanner', 'pc ', 'webcam')),
        ('perkakas', ('obeng', 'tang ', 'kabel', 'adaptor', 'adapter', 'charger', 'toolbox')),
    ]
    for item in InventarisBarang.objects.all().iterator():
        name = item.nama.lower()
        category = next((key for key, words in rules if any(word in name for word in words)), 'lainnya')
        InventarisBarang.objects.filter(pk=item.pk).update(kategori=category)


class Migration(migrations.Migration):
    dependencies = [('inventaris', '0009_fotoinventarisbarang')]

    operations = [
        migrations.AddField(
            model_name='lokasi', name='foto',
            field=models.ImageField(blank=True, null=True, upload_to='lokasi/'),
        ),
        migrations.AddField(
            model_name='lokasi', name='petunjuk_penyimpanan',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='inventarisbarang', name='kategori',
            field=models.CharField(
                choices=[('sensor', 'Sensor'), ('mikrokontroler', 'Mikrokontroler & IoT'),
                         ('komputer', 'Komputer & Periferal'), ('jaringan', 'Jaringan'),
                         ('elektronika', 'Elektronika & Alat Ukur'),
                         ('audio_visual', 'Audio, Video & Kamera'),
                         ('perkakas', 'Perkakas & Kelengkapan'), ('lainnya', 'Lainnya')],
                db_index=True, default='lainnya', max_length=20,
            ),
        ),
        migrations.RunPython(kelompokkan_barang, migrations.RunPython.noop),
    ]
