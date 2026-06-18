from django.contrib import admin

from .models import PeminjamanAlat


@admin.register(PeminjamanAlat)
class PeminjamanAlatAdmin(admin.ModelAdmin):
    list_display = ('barang', 'nama_peminjam', 'nim', 'no_hp', 'jumlah', 'tanggal_pinjam', 'tanggal_kembali', 'status')
    list_filter = ('status', 'tanggal_pinjam', 'tanggal_kembali')
    search_fields = ('nama_peminjam', 'nim', 'no_hp', 'barang__nama', 'barang__kode_barang')
