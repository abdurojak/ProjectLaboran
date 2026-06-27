from django.contrib import admin

from .models import AbsensiAsleb, Asleb, HonorAsleb, PengaturanAbsensiAsleb


@admin.register(Asleb)
class AslebAdmin(admin.ModelAdmin):
    list_display = ('nama', 'nim', 'no_hp', 'program_studi', 'matkul', 'semester', 'status')
    list_filter = ('status', 'program_studi', 'matkul', 'semester')
    search_fields = ('nama', 'nim', 'no_hp', 'email', 'program_studi', 'matkul')


@admin.register(HonorAsleb)
class HonorAslebAdmin(admin.ModelAdmin):
    list_display = ('asleb', 'bulan', 'level', 'total_pertemuan', 'jumlah', 'status', 'pic_transfer')
    list_filter = ('status', 'level', 'bulan')
    search_fields = ('asleb__nama', 'asleb__nim', 'keterangan')
    readonly_fields = ('jumlah',)


@admin.register(AbsensiAsleb)
class AbsensiAslebAdmin(admin.ModelAdmin):
    list_display = ('asleb', 'tanggal_praktikum', 'modul', 'materi_praktikum', 'dibuat_pada')
    list_filter = ('tanggal_praktikum', 'modul')
    search_fields = ('asleb__nama', 'asleb__nim', 'materi_praktikum')


@admin.register(PengaturanAbsensiAsleb)
class PengaturanAbsensiAslebAdmin(admin.ModelAdmin):
    list_display = ('dibuka', 'diperbarui_pada')

    def has_add_permission(self, request):
        return not PengaturanAbsensiAsleb.objects.exists()
