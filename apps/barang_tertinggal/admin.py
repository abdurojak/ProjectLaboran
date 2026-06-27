from django.contrib import admin

from .models import BarangTertinggal


@admin.register(BarangTertinggal)
class BarangTertinggalAdmin(admin.ModelAdmin):
    list_display = (
        'kode_barang_tertinggal',
        'nama_barang',
        'jenis_barang',
        'jumlah_barang',
        'tanggal_ditemukan',
        'tanggal_diambil',
        'nama_pemilik',
        'status',
    )
    list_filter = ('status', 'jenis_barang', 'tanggal_ditemukan')
    search_fields = ('kode_barang_tertinggal', 'nama_barang', 'jenis_barang', 'nama_pemilik')
