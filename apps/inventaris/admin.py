from django.contrib import admin

from .models import Barang, InventarisBarang, Lokasi, PaketBarang, PaketBarangItem


class PaketBarangItemInline(admin.TabularInline):
    model = PaketBarangItem
    extra = 1


@admin.register(Lokasi)
class LokasiAdmin(admin.ModelAdmin):
    list_display = ('kode_lokasi', 'nama_lokasi', 'ukuran_lokasi')
    search_fields = ('kode_lokasi', 'nama_lokasi')
    readonly_fields = ('kode_lokasi',)


@admin.register(InventarisBarang)
class InventarisBarangAdmin(admin.ModelAdmin):
    list_display = ('kode_inventaris', 'nama', 'jumlah')
    search_fields = ('kode_inventaris', 'nama')
    readonly_fields = ('kode_inventaris',)


@admin.register(Barang)
class BarangAdmin(admin.ModelAdmin):
    list_display = ('kode_barang', 'inventaris', 'lokasi', 'kondisi')
    list_filter = ('kondisi', 'inventaris')
    search_fields = ('kode_barang', 'inventaris__kode_inventaris', 'inventaris__nama', 'lokasi__nama_lokasi', 'lokasi__kode_lokasi')


@admin.register(PaketBarang)
class PaketBarangAdmin(admin.ModelAdmin):
    list_display = ('kode_paket', 'nama', 'aktif')
    list_filter = ('aktif',)
    search_fields = ('kode_paket', 'nama')
    readonly_fields = ('kode_paket',)
    inlines = [PaketBarangItemInline]
