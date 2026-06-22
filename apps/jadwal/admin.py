from django.contrib import admin

from .models import JadwalPraktikum


@admin.register(JadwalPraktikum)
class JadwalPraktikumAdmin(admin.ModelAdmin):
    list_display = ('mata_kuliah', 'kelas', 'tanggal', 'waktu_mulai', 'letak_ruangan', 'pengampu')
    list_filter = ('tanggal', 'letak_ruangan')
    search_fields = ('mata_kuliah', 'kelas', 'letak_ruangan', 'pengampu')

