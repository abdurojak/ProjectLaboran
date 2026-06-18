from django.contrib import admin

from .models import JadwalPraktikum


@admin.register(JadwalPraktikum)
class JadwalPraktikumAdmin(admin.ModelAdmin):
    list_display = ('mata_praktikum', 'kelas', 'tanggal', 'waktu_mulai', 'ruangan', 'pengampu')
    list_filter = ('tanggal', 'ruangan')
    search_fields = ('mata_praktikum', 'kelas', 'ruangan', 'pengampu')

