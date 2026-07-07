from django import forms

from .models import FotoRuanganLab


class FotoRuanganLabForm(forms.ModelForm):
    class Meta:
        model = FotoRuanganLab
        fields = ['gambar', 'judul', 'urutan']
        widgets = {
            'gambar': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'judul': forms.TextInput(attrs={'placeholder': 'Contoh: Tampak depan lab'}),
            'urutan': forms.NumberInput(attrs={'min': 0}),
        }

