from django.contrib import admin

from .models import JadwalPraktikum


@admin.register(JadwalPraktikum)
class JadwalPraktikumAdmin(admin.ModelAdmin):
    list_display = ('mata_kuliah', 'kelas', 'hari', 'waktu_mulai', 'ruangan', 'pengampu')
    list_filter = ('hari', 'ruangan')
    search_fields = ('mata_kuliah', 'kelas', 'ruangan__nama', 'pengampu')

