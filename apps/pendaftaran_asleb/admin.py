from django.contrib import admin

from .models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb, PeriodeAsleb


@admin.register(MataKuliahAsleb)
class MataKuliahAslebAdmin(admin.ModelAdmin):
    list_display = ('kode', 'nama', 'dosen', 'kelas', 'aktif')
    list_filter = ('aktif', 'nama', 'kelas')
    search_fields = ('kode', 'nama', 'dosen', 'kelas')


@admin.register(PendaftaranAsleb)
class PendaftaranAslebAdmin(admin.ModelAdmin):
    list_display = ('nama', 'nim', 'periode', 'matkul', 'program_studi', 'semester', 'rekening', 'status', 'tanggal_daftar')
    list_filter = ('periode', 'status', 'matkul', 'program_studi', 'semester')
    search_fields = ('nama', 'nim', 'no_hp', 'email', 'program_studi', 'matkul', 'rekening')


@admin.register(PengaturanPendaftaranAsleb)
class PengaturanPendaftaranAslebAdmin(admin.ModelAdmin):
    list_display = ('status_pendaftaran', 'diperbarui_pada')

    def has_add_permission(self, request):
        return not PengaturanPendaftaranAsleb.objects.exists()

    def status_pendaftaran(self, obj):
        return 'Dibuka' if obj.dibuka else 'Ditutup'

    status_pendaftaran.short_description = 'Status'


@admin.register(PeriodeAsleb)
class PeriodeAslebAdmin(admin.ModelAdmin):
    list_display = ('nama', 'mulai', 'selesai', 'pendaftaran_mulai', 'pendaftaran_selesai', 'pendaftaran_dibuka')
    list_filter = ('tahun', 'semester')
