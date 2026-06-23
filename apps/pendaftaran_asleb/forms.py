from django import forms

from .models import MataKuliahAsleb, PendaftaranAsleb


class PendaftaranAslebForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['matkul'].queryset = MataKuliahAsleb.objects.filter(aktif=True)
        self.fields['matkul'].empty_label = 'Pilih mata kuliah'

    class Meta:
        model = PendaftaranAsleb
        fields = [
            'nama',
            'nim',
            'no_hp',
            'email',
            'program_studi',
            'semester',
            'matkul',
            'cv',
            'transkrip',
            'rekening',
            'alasan',
            'status',
        ]
        widgets = {
            'nama': forms.TextInput(attrs={'placeholder': 'Nama lengkap calon asleb'}),
            'nim': forms.TextInput(attrs={'placeholder': 'NIM mahasiswa'}),
            'no_hp': forms.TextInput(attrs={'placeholder': 'Nomor HP aktif'}),
            'program_studi': forms.TextInput(attrs={'placeholder': 'Contoh: Rekayasa Perangkat Lunak'}),
            'matkul': forms.Select(attrs={'class': 'min-h-12'}),
            'rekening': forms.TextInput(attrs={'placeholder': 'Contoh: BCA 123456789 a.n. Nama Mahasiswa'}),
            'alasan': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Alasan atau catatan pendaftaran'}),
        }


class PendaftaranAslebPublicForm(PendaftaranAslebForm):
    class Meta(PendaftaranAslebForm.Meta):
        fields = [
            'nama',
            'nim',
            'no_hp',
            'email',
            'program_studi',
            'semester',
            'matkul',
            'cv',
            'transkrip',
            'rekening',
            'alasan',
        ]


class MataKuliahAslebForm(forms.ModelForm):
    class Meta:
        model = MataKuliahAsleb
        fields = ['kode', 'nama', 'dosen', 'kelas', 'aktif']
        widgets = {
            'kode': forms.TextInput(attrs={'placeholder': 'Contoh: PW_TIF01_NAMA'}),
            'nama': forms.TextInput(attrs={'placeholder': 'Nama mata kuliah'}),
            'dosen': forms.TextInput(attrs={'placeholder': 'Nama dosen'}),
            'kelas': forms.TextInput(attrs={'placeholder': 'Contoh: TIF-01'}),
        }
