from django import forms
from apps.pengguna.models import Pengguna

from .models import FotoRuanganLab, RuanganLab


class RuanganLabForm(forms.ModelForm):
    class Meta:
        model = RuanganLab
        fields = [
            'nama', 'kode', 'kepala_lab', 'laboran', 'laboran_akun', 'kapasitas', 'kapasitas_tak_terbatas',
            'warna', 'deskripsi', 'aktif',
        ]
        widgets = {
            'nama': forms.TextInput(attrs={'placeholder': 'Contoh: Lab Pemrograman'}),
            'kode': forms.TextInput(attrs={'placeholder': 'Contoh: LAB-PROG'}),
            'kepala_lab': forms.TextInput(attrs={'placeholder': 'Nama kepala laboratorium'}),
            'laboran': forms.TextInput(attrs={'placeholder': 'Nama laboran penanggung jawab'}),
            'laboran_akun': forms.SelectMultiple(attrs={'size': 5}),
            'kapasitas': forms.NumberInput(attrs={'min': 0}),
            'deskripsi': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        current_pengguna = kwargs.pop('current_pengguna', None)
        super().__init__(*args, **kwargs)
        if getattr(current_pengguna, 'role', None) == 'admin':
            self.fields['laboran_akun'].queryset = Pengguna.objects.filter(role='laboran', is_verified=True).order_by('nama_pengguna')
        else:
            self.fields.pop('laboran_akun')


class FotoRuanganLabForm(forms.ModelForm):
    class Meta:
        model = FotoRuanganLab
        fields = ['gambar', 'judul', 'urutan']
        widgets = {
            'gambar': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'judul': forms.TextInput(attrs={'placeholder': 'Contoh: Tampak depan lab'}),
            'urutan': forms.NumberInput(attrs={'min': 0}),
        }

