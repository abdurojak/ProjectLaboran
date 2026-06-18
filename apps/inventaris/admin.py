from django.contrib import admin

from .models import Barang


@admin.register(Barang)
class BarangAdmin(admin.ModelAdmin):
    list_display = ('kode_barang', 'nama', 'jumlah', 'lokasi', 'kondisi')
    list_filter = ('kondisi',)
    search_fields = ('kode_barang', 'nama', 'lokasi')

# Register your models here.
