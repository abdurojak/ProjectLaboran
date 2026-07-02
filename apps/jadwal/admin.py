from django.contrib import admin

from .models import JadwalPraktikum, PermintaanPerubahanJadwal


@admin.register(JadwalPraktikum)
class JadwalPraktikumAdmin(admin.ModelAdmin):
    list_display = ('mata_kuliah', 'kelas', 'hari', 'waktu_mulai', 'ruangan', 'ruangan_tambahan', 'pengampu', 'status')
    list_filter = ('hari', 'ruangan', 'ruangan_tambahan', 'status')
    search_fields = ('mata_kuliah', 'kelas', 'ruangan__nama', 'ruangan_tambahan__nama', 'pengampu')


@admin.register(PermintaanPerubahanJadwal)
class PermintaanPerubahanJadwalAdmin(admin.ModelAdmin):
    list_display = ('jadwal', 'diajukan_oleh', 'hari', 'waktu_mulai', 'status', 'dibuat_pada')
    list_filter = ('status', 'hari')
    search_fields = ('jadwal__mata_kuliah', 'diajukan_oleh__nama_pengguna')

