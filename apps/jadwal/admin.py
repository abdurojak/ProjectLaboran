from django.contrib import admin

from .models import JadwalPraktikum


@admin.register(JadwalPraktikum)
class JadwalPraktikumAdmin(admin.ModelAdmin):
    list_display = ('mata_kuliah', 'kelas', 'hari', 'waktu_mulai', 'ruangan', 'ruangan_tambahan', 'pengampu', 'status')
    list_filter = ('hari', 'ruangan', 'ruangan_tambahan', 'status')
    search_fields = ('mata_kuliah', 'kelas', 'ruangan__nama', 'ruangan_tambahan__nama', 'pengampu')

