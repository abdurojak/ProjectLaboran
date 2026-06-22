from django import forms

from .models import JadwalPraktikum


class JadwalPraktikumForm(forms.ModelForm):
    class Meta:
        model = JadwalPraktikum
        fields = [
            'mata_kuliah',
            'kelas',
            'letak_ruangan',
            'pengampu',
            'tanggal',
            'waktu_mulai',
            'waktu_selesai',
            'catatan',
        ]
        widgets = {
            'mata_kuliah': forms.TextInput(attrs={'placeholder': 'Contoh: Pemrograman Web'}),
            'kelas': forms.TextInput(attrs={'placeholder': 'Contoh: TI 4A'}),
            'letak_ruangan': forms.TextInput(attrs={'placeholder': 'Contoh: Lab Pemrograman'}),
            'pengampu': forms.TextInput(attrs={'placeholder': 'Nama dosen/asleb pengampu'}),
            'tanggal': forms.DateInput(attrs={'type': 'date'}),
            'waktu_mulai': forms.TimeInput(attrs={'type': 'time'}),
            'waktu_selesai': forms.TimeInput(attrs={'type': 'time'}),
            'catatan': forms.Textarea(attrs={'rows': 4}),
        }

