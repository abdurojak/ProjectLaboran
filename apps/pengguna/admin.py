from django.contrib import admin

from .models import Fakultas, PengalamanPengguna, Pengguna, Prodi


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


@admin.register(PengalamanPengguna)
class PengalamanPenggunaAdmin(admin.ModelAdmin):
    list_display = ('pengguna', 'kategori', 'jabatan', 'organisasi', 'tanggal_mulai', 'tanggal_selesai', 'masih_berjalan', 'otomatis')
    list_filter = ('kategori', 'otomatis', 'masih_berjalan', 'organisasi')
    search_fields = ('pengguna__nama_pengguna', 'pengguna__nim_nik', 'jabatan', 'organisasi')
