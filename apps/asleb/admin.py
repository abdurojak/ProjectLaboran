from django.contrib import admin

<<<<<<< HEAD
from .models import AbsensiAsleb, Asleb, HonorAsleb, PengaturanAbsensiAsleb
=======
from .models import AbsensiAsleb, Asleb, HonorAsleb, PengaturanAbsensiAsleb, SuratHonorAsleb
>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271


@admin.register(Asleb)
class AslebAdmin(admin.ModelAdmin):
    list_display = ('nama', 'nim', 'no_hp', 'program_studi', 'matkul', 'semester', 'status')
    list_filter = ('status', 'program_studi', 'matkul', 'semester')
    search_fields = ('nama', 'nim', 'no_hp', 'email', 'program_studi', 'matkul')


@admin.register(HonorAsleb)
class HonorAslebAdmin(admin.ModelAdmin):
<<<<<<< HEAD
    list_display = ('asleb', 'bulan', 'level', 'total_pertemuan', 'jumlah', 'status', 'pic_transfer')
    list_filter = ('status', 'level', 'bulan')
    search_fields = ('asleb__nama', 'asleb__nim', 'keterangan')
    readonly_fields = ('jumlah',)


=======
    list_display = ('asleb', 'bulan', 'level', 'total_pertemuan', 'jumlah', 'status', 'assigned_laboran', 'pic_transfer')
    list_filter = ('status', 'level', 'bulan', 'assigned_laboran')
    search_fields = ('asleb__nama', 'asleb__nim', 'assigned_laboran__nama_pengguna', 'keterangan')
    readonly_fields = ('jumlah',)


@admin.register(SuratHonorAsleb)
class SuratHonorAslebAdmin(admin.ModelAdmin):
    list_display = ('nomor_surat', 'bulan', 'jumlah_asleb', 'total_honor', 'dibuat_oleh', 'expires_at', 'dibuat_pada')
    list_filter = ('bulan', 'expires_at', 'dibuat_oleh')
    search_fields = ('nomor_surat', 'perihal', 'dibuat_oleh__nama_pengguna')
    readonly_fields = ('file_pdf', 'total_honor', 'jumlah_asleb', 'expires_at', 'dibuat_pada', 'diperbarui_pada')


>>>>>>> c12dcba654e9562f68a0caec0c103cefae955271
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
