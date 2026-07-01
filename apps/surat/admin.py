from django.contrib import admin

from .models import SuratPengadaan


@admin.register(SuratPengadaan)
class SuratPengadaanAdmin(admin.ModelAdmin):
    list_display = ('nomor', 'tanggal', 'hal', 'dibuat_oleh')
    search_fields = ('nomor', 'hal', 'nama_penandatangan')
    list_filter = ('tanggal',)
