from django import forms

from .models import KegiatanKalender


class KegiatanKalenderForm(forms.ModelForm):
    class Meta:
        model = KegiatanKalender
        fields = [
            'judul',
            'tanggal',
            'waktu_mulai',
            'waktu_selesai',
            'lokasi',
            'deskripsi',
            'tampilkan_notifikasi',
        ]
        widgets = {
            'tanggal': forms.DateInput(attrs={'type': 'date'}),
            'waktu_mulai': forms.TimeInput(attrs={'type': 'time'}),
            'waktu_selesai': forms.TimeInput(attrs={'type': 'time'}),
            'deskripsi': forms.Textarea(attrs={'rows': 4}),
        }

