from django.contrib import admin

from .models import RuanganLab


@admin.register(RuanganLab)
class RuanganLabAdmin(admin.ModelAdmin):
    list_display = ('kode', 'nama', 'kapasitas', 'warna', 'aktif')
    list_filter = ('aktif', 'warna')
    search_fields = ('kode', 'nama', 'deskripsi')

