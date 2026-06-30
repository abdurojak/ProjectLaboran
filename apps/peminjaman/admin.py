from django.contrib import admin

from .models import PeminjamanAlat, PeminjamanTransaksi


class PeminjamanAlatInline(admin.TabularInline):
    model = PeminjamanAlat
    extra = 0
    fields = ('barang', 'status', 'paket')
    readonly_fields = ('barang', 'status', 'paket')


@admin.register(PeminjamanTransaksi)
class PeminjamanTransaksiAdmin(admin.ModelAdmin):
    list_display = ('kode_pinjam', 'nama_peminjam', 'nim', 'tanggal_pinjam', 'tanggal_kembali')
    search_fields = ('kode_pinjam', 'nama_peminjam', 'nim', 'no_hp')
    readonly_fields = ('kode_pinjam',)
    inlines = [PeminjamanAlatInline]


@admin.register(PeminjamanAlat)
class PeminjamanAlatAdmin(admin.ModelAdmin):
    list_display = ('kode_pinjam', 'barang', 'nama_peminjam', 'nim', 'no_hp', 'tanggal_pinjam', 'tanggal_kembali', 'status')
    list_filter = ('status', 'tanggal_pinjam', 'tanggal_kembali')
    search_fields = ('kode_pinjam', 'nama_peminjam', 'nim', 'no_hp', 'barang__nama', 'barang__kode_barang')
