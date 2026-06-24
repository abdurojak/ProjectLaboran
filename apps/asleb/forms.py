from django import forms

from .models import AbsensiAsleb, Asleb, HonorAsleb


class AslebForm(forms.ModelForm):
    class Meta:
        model = Asleb
        fields = [
            'nama',
            'nim',
            'no_hp',
            'email',
            'program_studi',
            'matkul',
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
            'matkul': forms.TextInput(attrs={'placeholder': 'Contoh: Pemrograman Web'}),
            'tanggal_bergabung': forms.DateInput(attrs={'type': 'date'}),
            'catatan': forms.Textarea(attrs={'rows': 4}),
        }


class HonorAslebForm(forms.ModelForm):
    class Meta:
        model = HonorAsleb
        fields = [
            'asleb',
            'bulan',
            'level',
            'jumlah_praktikum',
            'total_pertemuan',
            'pic_transfer',
            'status',
            'keterangan',
        ]
        widgets = {
            'bulan': forms.DateInput(attrs={'type': 'date'}),
            'keterangan': forms.Textarea(attrs={'rows': 3}),
        }


class AbsensiAslebForm(forms.ModelForm):
    class Meta:
        model = AbsensiAsleb
        fields = [
            'tanggal_praktikum',
            'modul',
            'materi_praktikum',
            'pekerjaan',
            'file_modul',
            'bukti_video',
        ]
        widgets = {
            'tanggal_praktikum': forms.DateInput(attrs={'type': 'date'}),
            'pekerjaan': forms.Textarea(attrs={'rows': 4}),
            'file_modul': forms.FileInput(attrs={'accept': '.pdf,.doc,.docx,.ppt,.pptx,.zip'}),
            'bukti_video': forms.FileInput(attrs={'accept': 'video/*'}),
        }

    def __init__(self, *args, **kwargs):
        self.asleb = kwargs.pop('asleb')
        super().__init__(*args, **kwargs)
        used_modules = set(AbsensiAsleb.objects.filter(asleb=self.asleb).values_list('modul', flat=True))
        current_module = self.instance.modul if self.instance and self.instance.pk else None
        choices = [
            (value, label)
            for value, label in AbsensiAsleb.MODUL_CHOICES
            if value not in used_modules or value == current_module
        ]
        self.fields['modul'].choices = [('', 'Pilih modul'), *choices]

    def clean_modul(self):
        modul = self.cleaned_data['modul']
        duplicate = AbsensiAsleb.objects.filter(asleb=self.asleb, modul=modul)
        if self.instance and self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)

        if duplicate.exists():
            raise forms.ValidationError('Modul ini sudah pernah diabsen. Pilih modul lain.')

        return modul
