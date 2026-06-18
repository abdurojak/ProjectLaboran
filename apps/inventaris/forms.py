from django import forms

from .models import Barang


class BarangForm(forms.ModelForm):
    class Meta:
        model = Barang
        fields = ['nama', 'jumlah', 'lokasi', 'kondisi', 'foto', 'keterangan']
        widgets = {
            'keterangan': forms.Textarea(attrs={'rows': 4}),
        }
