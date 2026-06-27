from django.contrib import admin

from .models import KegiatanKalender


@admin.register(KegiatanKalender)
class KegiatanKalenderAdmin(admin.ModelAdmin):
    list_display = ('judul', 'tanggal', 'waktu_mulai', 'lokasi', 'tampilkan_notifikasi')
    list_filter = ('tanggal', 'tampilkan_notifikasi')
    search_fields = ('judul', 'lokasi', 'deskripsi')

