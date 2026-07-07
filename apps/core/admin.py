from django.contrib import admin

from .models import BugErrorLog, PercakapanBantuan, PesanBantuan


@admin.register(PercakapanBantuan)
class PercakapanBantuanAdmin(admin.ModelAdmin):
    list_display = ('pengguna', 'status', 'diperbarui_pada')
    list_filter = ('status',)
    search_fields = ('pengguna__nama_pengguna', 'pengguna__email')


@admin.register(PesanBantuan)
class PesanBantuanAdmin(admin.ModelAdmin):
    list_display = ('percakapan', 'pengirim', 'dibuat_pada')
    list_filter = ('pengirim',)
    search_fields = ('isi', 'percakapan__pengguna__nama_pengguna')


@admin.register(BugErrorLog)
class BugErrorLogAdmin(admin.ModelAdmin):
    list_display = ('judul', 'kategori', 'prioritas', 'status', 'dilaporkan_oleh', 'ditangani_oleh', 'dibuat_pada')
    list_filter = ('status', 'kategori', 'prioritas')
    search_fields = (
        'judul', 'lokasi', 'deskripsi',
        'dilaporkan_oleh__nama_pengguna', 'dilaporkan_oleh__email',
        'ditangani_oleh__nama_pengguna', 'ditangani_oleh__email',
    )
    readonly_fields = ('dibuat_pada', 'diperbarui_pada')
