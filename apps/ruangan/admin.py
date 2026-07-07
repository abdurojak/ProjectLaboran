from django.contrib import admin

from .models import FotoRuanganLab, GrupRuanganGabungan, RuanganLab


class FotoRuanganLabInline(admin.TabularInline):
    model = FotoRuanganLab
    extra = 1
    fields = ('gambar', 'judul', 'urutan')


@admin.register(RuanganLab)
class RuanganLabAdmin(admin.ModelAdmin):
    list_display = ('kode', 'nama', 'kapasitas', 'warna', 'aktif')
    list_filter = ('aktif', 'warna')
    search_fields = ('kode', 'nama', 'deskripsi')
    inlines = (FotoRuanganLabInline,)


@admin.register(FotoRuanganLab)
class FotoRuanganLabAdmin(admin.ModelAdmin):
    list_display = ('ruangan', 'judul', 'urutan', 'dibuat_pada')
    list_filter = ('ruangan',)
    search_fields = ('ruangan__nama', 'ruangan__kode', 'judul')


@admin.register(GrupRuanganGabungan)
class GrupRuanganGabunganAdmin(admin.ModelAdmin):
    list_display = ('nama', 'aktif', 'daftar_ruangan')
    list_filter = ('aktif',)
    search_fields = ('nama', 'deskripsi', 'ruangan__kode', 'ruangan__nama')
    filter_horizontal = ('ruangan',)

    def daftar_ruangan(self, obj):
        return ' + '.join(obj.ruangan.values_list('nama', flat=True))

    daftar_ruangan.short_description = 'Ruangan'

