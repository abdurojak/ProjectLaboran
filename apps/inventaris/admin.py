from django.contrib import admin

from .models import Barang, Lokasi


@admin.register(Lokasi)
class LokasiAdmin(admin.ModelAdmin):
    list_display = ('kode_lokasi', 'nama_lokasi', 'ukuran_lokasi')
    search_fields = ('kode_lokasi', 'nama_lokasi')
    readonly_fields = ('kode_lokasi',)


@admin.register(Barang)
class BarangAdmin(admin.ModelAdmin):
    list_display = ('kode_barang', 'nama', 'jumlah', 'lokasi', 'kondisi')
    list_filter = ('kondisi',)
    search_fields = ('kode_barang', 'nama', 'lokasi__nama_lokasi', 'lokasi__kode_lokasi')

# Register your models here.
