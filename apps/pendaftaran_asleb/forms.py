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
    def __init__(self, *args, **kwargs):
        self.current_pengguna = kwargs.pop('current_pengguna', None)
        super().__init__(*args, **kwargs)

        if self.current_pengguna:
            auto_values = {
                'nama': self.current_pengguna.nama_pengguna,
                'nim': self.current_pengguna.nim_nik,
                'email': self.current_pengguna.email,
                'program_studi': self.current_pengguna.prodi,
            }

            for field_name, value in auto_values.items():
                self.fields[field_name].initial = value

            for field_name in ['nama', 'nim']:
                self.fields[field_name].disabled = True
                self.fields[field_name].help_text = 'Otomatis dari akun login.'

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

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.current_pengguna:
            instance.nama = self.current_pengguna.nama_pengguna
            instance.nim = self.current_pengguna.nim_nik
            instance.email = self.current_pengguna.email
            instance.program_studi = self.current_pengguna.prodi

        if commit:
            instance.save()
            self.save_m2m()

        return instance


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
