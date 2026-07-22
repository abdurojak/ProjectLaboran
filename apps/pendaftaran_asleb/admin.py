from django.contrib import admin

from .models import (
    AslabAssignment,
    AslabOffer,
    AslabReplacement,
    AslabReplacementAudit,
    AslabSlot,
    LimitedReplacementOpening,
    MataKuliahAsleb,
    PendaftaranAsleb,
    PengaturanBiayaTransfer,
    PengaturanPendaftaranAsleb,
    PeriodeAsleb,
    RiwayatAsleb,
)


class ReadOnlyWorkflowAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AslabReplacement)
class AslabReplacementAdmin(ReadOnlyWorkflowAdmin):
    list_display = ('outgoing_assignment', 'slot', 'effective_date', 'method', 'status', 'created_at')
    list_filter = ('method', 'status', 'effective_date')
    list_select_related = ('slot__periode', 'slot__matkul', 'outgoing_assignment__asleb', 'created_by')
    readonly_fields = [field.name for field in AslabReplacement._meta.fields]


@admin.register(AslabOffer)
class AslabOfferAdmin(ReadOnlyWorkflowAdmin):
    list_display = ('candidate', 'replacement', 'status', 'deadline', 'verified_at')
    list_filter = ('status',)
    list_select_related = (
        'candidate', 'replacement__slot',
        'replacement__outgoing_assignment__asleb',
        'replacement__outgoing_assignment__slot',
        'replacement__outgoing_assignment__slot__periode',
        'replacement__outgoing_assignment__slot__matkul',
        'registration', 'verified_by',
    )
    readonly_fields = [field.name for field in AslabOffer._meta.fields]


@admin.register(LimitedReplacementOpening)
class LimitedReplacementOpeningAdmin(ReadOnlyWorkflowAdmin):
    list_display = ('replacement', 'opens_at', 'closes_at', 'status')
    list_filter = ('status',)
    list_select_related = (
        'replacement__slot',
        'replacement__outgoing_assignment__asleb',
        'replacement__outgoing_assignment__slot',
        'replacement__outgoing_assignment__slot__periode',
        'replacement__outgoing_assignment__slot__matkul',
    )
    readonly_fields = [field.name for field in LimitedReplacementOpening._meta.fields]


@admin.register(AslabReplacementAudit)
class AslabReplacementAuditAdmin(ReadOnlyWorkflowAdmin):
    list_display = ('replacement', 'action', 'previous_state', 'new_state', 'actor', 'created_at')
    list_filter = ('action', 'new_state')
    list_select_related = (
        'replacement__slot',
        'replacement__outgoing_assignment__asleb',
        'replacement__outgoing_assignment__slot',
        'replacement__outgoing_assignment__slot__periode',
        'replacement__outgoing_assignment__slot__matkul',
        'actor',
    )
    readonly_fields = [field.name for field in AslabReplacementAudit._meta.fields]


@admin.register(AslabSlot)
class AslabSlotAdmin(admin.ModelAdmin):
    list_display = ('periode', 'matkul', 'nomor', 'status', 'dibuat_pada', 'diperbarui_pada')
    list_filter = ('periode', 'matkul', 'status', 'nomor')
    list_select_related = ('periode', 'matkul')
    readonly_fields = ('periode', 'matkul', 'nomor', 'status', 'dibuat_pada', 'diperbarui_pada')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AslabAssignment)
class AslabAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'periode', 'matkul', 'nomor_slot', 'asleb', 'status',
        'mulai_pada', 'berakhir_pada',
    )
    list_filter = ('slot__periode', 'slot__matkul', 'status')
    list_select_related = ('slot__periode', 'slot__matkul', 'asleb')
    readonly_fields = (
        'slot', 'active_slot', 'asleb', 'source_pendaftaran', 'mulai_pada',
        'berakhir_pada', 'status', 'alasan_berakhir', 'diakhiri_oleh',
        'menggantikan', 'dibuat_pada', 'diperbarui_pada',
    )

    @admin.display(ordering='slot__periode', description='Periode')
    def periode(self, obj):
        return obj.slot.periode

    @admin.display(ordering='slot__matkul', description='Mata Kuliah')
    def matkul(self, obj):
        return obj.slot.matkul

    @admin.display(ordering='slot__nomor', description='Slot')
    def nomor_slot(self, obj):
        return obj.slot.nomor

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MataKuliahAsleb)
class MataKuliahAslebAdmin(admin.ModelAdmin):
    list_display = ('kode', 'kode_mk', 'nama', 'sks', 'dosen', 'kelas', 'aktif')
    list_filter = ('aktif', 'nama', 'kelas')
    search_fields = ('kode', 'kode_mk', 'nama', 'dosen', 'kelas')


@admin.register(PendaftaranAsleb)
class PendaftaranAslebAdmin(admin.ModelAdmin):
    list_display = ('nama', 'nim', 'periode', 'matkul', 'program_studi', 'semester', 'rekening', 'status', 'tanggal_daftar')
    list_filter = ('periode', 'status', 'matkul', 'program_studi', 'semester')
    search_fields = ('nama', 'nim', 'no_hp', 'email', 'program_studi', 'matkul', 'rekening')


@admin.register(RiwayatAsleb)
class RiwayatAslebAdmin(admin.ModelAdmin):
    list_display = ('nama', 'nim', 'periode', 'matkul', 'metode_rekening', 'dibuat_pada')
    list_filter = ('periode', 'matkul', 'metode_rekening')
    search_fields = ('nama', 'nim', 'email', 'rekening', 'nama_pemilik_rekening')
    readonly_fields = (
        'nim', 'nama', 'email', 'periode', 'matkul', 'metode_rekening',
        'rekening', 'nama_pemilik_rekening', 'source_pendaftaran_id', 'dibuat_pada',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PengaturanBiayaTransfer)
class PengaturanBiayaTransferAdmin(admin.ModelAdmin):
    list_display = ('biaya_bni', 'biaya_bank_lain', 'biaya_dana', 'biaya_shopeepay', 'biaya_gopay', 'biaya_ovo', 'diperbarui_pada')

    def has_add_permission(self, request):
        return not PengaturanBiayaTransfer.objects.exists()


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
