from django import forms

from .models import BarangTertinggal


class BarangTertinggalForm(forms.ModelForm):
    class Meta:
        model = BarangTertinggal
        fields = [
            'nama_barang',
            'jenis_barang',
            'jumlah_barang',
            'foto',
            'tanggal_ditemukan',
            'tanggal_diambil',
            'nama_pemilik',
            'status',
        ]
        widgets = {
            'foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'tanggal_ditemukan': forms.DateInput(attrs={'type': 'date'}),
            'tanggal_diambil': forms.DateInput(attrs={'type': 'date'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        hapus_foto = self.data.get('hapus_foto') == '1'

        if hapus_foto:
            instance.foto = None

        if commit:
            instance.save()
            self.save_m2m()

        return instance
