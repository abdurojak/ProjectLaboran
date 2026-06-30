from django.contrib import admin

from .models import KegiatanKalender, Notifikasi


@admin.register(KegiatanKalender)
class KegiatanKalenderAdmin(admin.ModelAdmin):
    list_display = ('judul', 'tanggal', 'waktu_mulai', 'lokasi', 'tampilkan_notifikasi')
    list_filter = ('tanggal', 'tampilkan_notifikasi')
    search_fields = ('judul', 'lokasi', 'deskripsi')


@admin.register(Notifikasi)
class NotifikasiAdmin(admin.ModelAdmin):
    list_display = ('judul', 'pengguna', 'badge', 'source_updated_at', 'dibaca_pada')
    list_filter = ('badge', 'dibaca_pada', 'source_updated_at')
    search_fields = ('judul', 'deskripsi', 'pengguna__nama_pengguna', 'pengguna__nim_nik', 'source_key')
    readonly_fields = ('source_key', 'dibuat_pada', 'diperbarui_pada')

