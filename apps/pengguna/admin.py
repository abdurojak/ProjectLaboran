from django.contrib import admin

from .models import Pengguna


@admin.register(Pengguna)
class PenggunaAdmin(admin.ModelAdmin):
    list_display = ('kode_pengguna', 'nama_pengguna', 'nim_nik', 'email', 'no_hp', 'fakultas', 'prodi', 'gender', 'role')
    list_filter = ('role', 'gender', 'fakultas', 'prodi')
    search_fields = ('kode_pengguna', 'nama_pengguna', 'nim_nik', 'email', 'no_hp')
