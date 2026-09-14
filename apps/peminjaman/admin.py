from django.contrib import admin

from .models import PengajuanPerpanjangan, PengingatPeminjaman, PeminjamanAlat, PeminjamanTransaksi


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


@admin.register(PengajuanPerpanjangan)
class PengajuanPerpanjanganAdmin(admin.ModelAdmin):
    list_display = (
        'transaksi',
        'diajukan_oleh',
        'tanggal_kembali_diminta',
        'kondisi_barang',
        'status',
        'ditinjau_oleh',
    )
    list_filter = ('status', 'kondisi_barang', 'pernyataan_jujur', 'dibuat_pada')
    search_fields = ('transaksi__kode_pinjam', 'transaksi__nim', 'diajukan_oleh__nama_pengguna')
    readonly_fields = ('dibuat_pada', 'diperbarui_pada', 'ditinjau_pada')


@admin.register(PengingatPeminjaman)
class PengingatPeminjamanAdmin(admin.ModelAdmin):
    list_display = ('transaksi', 'tanggal', 'jenis', 'dikirim_pada')
    list_filter = ('jenis', 'tanggal')
    search_fields = ('transaksi__kode_pinjam', 'transaksi__nim')
    readonly_fields = ('transaksi', 'tanggal', 'jenis', 'dikirim_pada')
