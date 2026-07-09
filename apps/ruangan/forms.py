from django import forms

from .models import FotoRuanganLab, RuanganLab


class RuanganLabForm(forms.ModelForm):
    class Meta:
        model = RuanganLab
        fields = ['nama', 'kode', 'kepala_lab', 'kapasitas', 'warna', 'deskripsi', 'aktif']
        widgets = {
            'nama': forms.TextInput(attrs={'placeholder': 'Contoh: Lab Pemrograman'}),
            'kode': forms.TextInput(attrs={'placeholder': 'Contoh: LAB-PROG'}),
            'kepala_lab': forms.TextInput(attrs={'placeholder': 'Nama kepala laboratorium'}),
            'kapasitas': forms.NumberInput(attrs={'min': 0}),
            'deskripsi': forms.Textarea(attrs={'rows': 4}),
        }


class FotoRuanganLabForm(forms.ModelForm):
    class Meta:
        model = FotoRuanganLab
        fields = ['gambar', 'judul', 'urutan']
        widgets = {
            'gambar': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'judul': forms.TextInput(attrs={'placeholder': 'Contoh: Tampak depan lab'}),
            'urutan': forms.NumberInput(attrs={'min': 0}),
        }

