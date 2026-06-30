from django.contrib import admin

from .models import (
    AbsensiAsleb,
    Asleb,
    HonorAsleb,
    ModulPraktikum,
    HasilPraktikumMahasiswa,
    PesertaPraktikum,
    PengaturanAbsensiAsleb,
    PengingatAbsensiAsleb,
    SuratHonorAsleb,
)


@admin.register(Asleb)
class AslebAdmin(admin.ModelAdmin):
    list_display = ('nama', 'nim', 'no_hp', 'program_studi', 'matkul', 'semester', 'status')
    list_filter = ('status', 'program_studi', 'matkul', 'semester')
    search_fields = ('nama', 'nim', 'no_hp', 'email', 'program_studi', 'matkul')


@admin.register(HonorAsleb)
class HonorAslebAdmin(admin.ModelAdmin):
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


@admin.register(AbsensiAsleb)
class AbsensiAslebAdmin(admin.ModelAdmin):
    list_display = ('asleb', 'tanggal_praktikum', 'modul', 'materi_praktikum', 'dibuat_pada')
    list_filter = ('tanggal_praktikum', 'modul')
    search_fields = ('asleb__nama', 'asleb__nim', 'materi_praktikum')


@admin.register(ModulPraktikum)
class ModulPraktikumAdmin(admin.ModelAdmin):
    list_display = ('nomor', 'judul', 'matkul', 'diunggah_oleh', 'diperbarui_pada')
    list_filter = ('matkul',)
    search_fields = ('judul', 'matkul__nama', 'matkul__kode')


@admin.register(PesertaPraktikum)
class PesertaPraktikumAdmin(admin.ModelAdmin):
    list_display = ('nim', 'nama', 'matkul', 'aktif', 'pengguna')
    list_filter = ('aktif', 'matkul')
    search_fields = ('nim', 'nama', 'matkul__nama', 'matkul__kelas')


@admin.register(HasilPraktikumMahasiswa)
class HasilPraktikumMahasiswaAdmin(admin.ModelAdmin):
    list_display = ('peserta', 'modul', 'tanggal_praktikum', 'status_absensi', 'nilai', 'dicatat_oleh')
    list_filter = ('status_absensi', 'modul__matkul', 'modul')
    search_fields = ('peserta__nim', 'peserta__nama', 'modul__judul')


@admin.register(PengaturanAbsensiAsleb)
class PengaturanAbsensiAslebAdmin(admin.ModelAdmin):
    list_display = ('dibuka', 'diperbarui_pada')

    def has_add_permission(self, request):
        return not PengaturanAbsensiAsleb.objects.exists()


@admin.register(PengingatAbsensiAsleb)
class PengingatAbsensiAslebAdmin(admin.ModelAdmin):
    list_display = ('asleb', 'jadwal', 'tanggal', 'tahap', 'dikirim_pada')
    list_filter = ('tanggal', 'tahap')
    search_fields = ('asleb__nama', 'asleb__nim', 'jadwal__mata_kuliah')
