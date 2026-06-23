from django.contrib import admin

from .models import MataKuliahAsleb, PendaftaranAsleb


@admin.register(MataKuliahAsleb)
class MataKuliahAslebAdmin(admin.ModelAdmin):
    list_display = ('kode', 'nama', 'dosen', 'kelas', 'aktif')
    list_filter = ('aktif', 'nama', 'kelas')
    search_fields = ('kode', 'nama', 'dosen', 'kelas')


@admin.register(PendaftaranAsleb)
class PendaftaranAslebAdmin(admin.ModelAdmin):
    list_display = ('nama', 'nim', 'matkul', 'program_studi', 'semester', 'rekening', 'status', 'tanggal_daftar')
    list_filter = ('status', 'matkul', 'program_studi', 'semester')
    search_fields = ('nama', 'nim', 'no_hp', 'email', 'program_studi', 'matkul', 'rekening')
