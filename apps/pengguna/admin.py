from django.contrib import admin

from .models import Fakultas, Pengguna, Prodi


@admin.register(Fakultas)
class FakultasAdmin(admin.ModelAdmin):
    list_display = ('nama', 'aktif', 'diperbarui_pada')
    list_filter = ('aktif',)
    search_fields = ('nama',)


@admin.register(Prodi)
class ProdiAdmin(admin.ModelAdmin):
    list_display = ('nama', 'aktif', 'diperbarui_pada')
    list_filter = ('aktif',)
    search_fields = ('nama',)


@admin.register(Pengguna)
class PenggunaAdmin(admin.ModelAdmin):
    list_display = ('kode_pengguna', 'nama_pengguna', 'nim_nik', 'email', 'no_hp', 'fakultas', 'prodi', 'gender', 'role')
    list_filter = ('role', 'gender', 'fakultas', 'prodi')
    search_fields = ('kode_pengguna', 'nama_pengguna', 'nim_nik', 'email', 'no_hp')
