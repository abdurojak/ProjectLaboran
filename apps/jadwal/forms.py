from django import forms

from .models import JadwalPraktikum


class JadwalPraktikumForm(forms.ModelForm):
    class Meta:
        model = JadwalPraktikum
        fields = [
            'mata_praktikum',
            'kelas',
            'ruangan',
            'pengampu',
            'tanggal',
            'waktu_mulai',
            'waktu_selesai',
            'catatan',
        ]
        widgets = {
            'tanggal': forms.DateInput(attrs={'type': 'date'}),
            'waktu_mulai': forms.TimeInput(attrs={'type': 'time'}),
            'waktu_selesai': forms.TimeInput(attrs={'type': 'time'}),
            'catatan': forms.Textarea(attrs={'rows': 4}),
        }

