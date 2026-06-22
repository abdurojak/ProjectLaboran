from django import forms

from .models import Asleb


class AslebForm(forms.ModelForm):
    class Meta:
        model = Asleb
        fields = [
            'nama',
            'nim',
            'no_hp',
            'email',
            'program_studi',
            'semester',
            'status',
            'tanggal_bergabung',
            'catatan',
        ]
        widgets = {
            'nama': forms.TextInput(attrs={'placeholder': 'Nama lengkap asleb'}),
            'nim': forms.TextInput(attrs={'placeholder': 'NIM mahasiswa'}),
            'no_hp': forms.TextInput(attrs={'placeholder': 'Nomor HP aktif'}),
            'program_studi': forms.TextInput(attrs={'placeholder': 'Contoh: Rekayasa Perangkat Lunak'}),
            'tanggal_bergabung': forms.DateInput(attrs={'type': 'date'}),
            'catatan': forms.Textarea(attrs={'rows': 4}),
        }
