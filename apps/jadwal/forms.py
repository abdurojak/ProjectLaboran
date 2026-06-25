from django import forms

from .models import JadwalPraktikum


class JadwalPraktikumForm(forms.ModelForm):
    class Meta:
        model = JadwalPraktikum
        fields = [
            'mata_kuliah',
            'kelas',
            'ruangan',
            'pengampu',
            'hari',
            'waktu_mulai',
            'waktu_selesai',
            'catatan',
        ]
        widgets = {
            'mata_kuliah': forms.TextInput(attrs={'placeholder': 'Contoh: Pemrograman Web'}),
            'kelas': forms.TextInput(attrs={'placeholder': 'Contoh: TI 4A'}),
            'pengampu': forms.TextInput(attrs={'placeholder': 'Nama dosen/asleb pengampu'}),
            'waktu_mulai': forms.TimeInput(attrs={'type': 'time', 'step': 1800, 'min': '07:30', 'max': '18:00'}),
            'waktu_selesai': forms.TimeInput(attrs={'type': 'time', 'step': 1800, 'min': '07:30', 'max': '18:00'}),
            'catatan': forms.Textarea(attrs={'rows': 4}),
        }

