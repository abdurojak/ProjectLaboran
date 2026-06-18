from django import forms

from .models import PeminjamanAlat


class PeminjamanAlatForm(forms.ModelForm):
    class Meta:
        model = PeminjamanAlat
        fields = [
            'barang',
            'nama_peminjam',
            'nim',
            'no_hp',
            'jumlah',
            'tanggal_pinjam',
            'tanggal_kembali',
            'status',
            'catatan',
        ]
        widgets = {
            'tanggal_pinjam': forms.DateInput(attrs={'type': 'date'}),
            'tanggal_kembali': forms.DateInput(attrs={'type': 'date'}),
            'catatan': forms.Textarea(attrs={'rows': 4}),
        }
