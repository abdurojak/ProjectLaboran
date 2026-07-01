import json

from django import forms

from .models import SuratPengadaan, default_items


DEFAULT_BODY = (
    'Sehubungan dengan persiapan pelaksanaan praktikum Semester Genap Tahun Akademik 2025/2026, '
    'kami mengajukan permohonan pengadaan kebutuhan fasilitas sebagai bahan praktikum di Laboratorium '
    'Jurusan Teknik Informatika. Pengadaan ini diperlukan karena keterbatasan stok bahan praktikum guna '
    'menunjang kelancaran dan optimalisasi kegiatan pembelajaran mahasiswa. Rincian kebutuhan terlampir sebagai berikut:'
)


class SuratPengadaanForm(forms.ModelForm):
    items_json = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = SuratPengadaan
        fields = [
            'nomor', 'tanggal', 'hal', 'lampiran', 'tujuan_jabatan', 'tujuan_instansi',
            'isi', 'nama_penandatangan', 'jabatan_penandatangan', 'laboratorium',
        ]
        widgets = {
            'tanggal': forms.DateInput(attrs={'type': 'date'}),
            'tujuan_instansi': forms.Textarea(attrs={'rows': 2}),
            'isi': forms.Textarea(attrs={'rows': 7}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['isi'].initial = DEFAULT_BODY
        self.fields['items_json'].initial = json.dumps(self.instance.items if self.instance.pk else default_items())

    def clean_items_json(self):
        try:
            items = json.loads(self.cleaned_data['items_json'])
        except (TypeError, ValueError, json.JSONDecodeError):
            raise forms.ValidationError('Daftar barang tidak valid.')
        cleaned = []
        for item in items:
            row = {key: str(item.get(key, '')).strip() for key in ('nama', 'spesifikasi', 'jumlah', 'keterangan')}
            if row['nama'] and row['jumlah']:
                cleaned.append(row)
        if not cleaned:
            raise forms.ValidationError('Tambahkan minimal satu barang.')
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.items = self.cleaned_data['items_json']
        if commit:
            instance.save()
        return instance
