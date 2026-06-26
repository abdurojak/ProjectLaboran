import hashlib

from django import forms

from apps.pengguna.models import Pengguna

from .models import AbsensiAsleb, Asleb, HonorAsleb, SuratHonorAsleb


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
            'jumlah_praktikum',
            'total_pertemuan',
            'metode_transfer',
            'nomor_transfer',
            'nama_pemilik_transfer',
            'tanggal_transfer',
            'bukti_transfer',
            'assigned_laboran',
            'pic_transfer',
            'status',
            'keterangan',
        ]
        widgets = {
            'bulan': forms.DateInput(attrs={'type': 'date'}),
            'tanggal_transfer': forms.DateInput(attrs={'type': 'date'}),
            'bukti_transfer': forms.FileInput(attrs={'accept': 'image/*,.pdf'}),
            'nomor_transfer': forms.TextInput(attrs={'placeholder': 'Contoh: BCA 123456789 / DANA 0812xxxx'}),
            'nama_pemilik_transfer': forms.TextInput(attrs={'placeholder': 'Nama sesuai rekening/e-wallet'}),
            'keterangan': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.current_pengguna = kwargs.pop('current_pengguna', None)
        super().__init__(*args, **kwargs)
        self.fields['assigned_laboran'].queryset = Pengguna.objects.filter(
            role='laboran',
            is_verified=True,
        ).order_by('nama_pengguna')
        self.fields['assigned_laboran'].required = False
        self.fields['assigned_laboran'].empty_label = 'Bagi otomatis ke laboran'
        if not self.current_pengguna or self.current_pengguna.role != 'admin':
            self.fields.pop('assigned_laboran', None)


class KonfirmasiTransferHonorForm(forms.ModelForm):
    class Meta:
        model = HonorAsleb
        fields = ['tanggal_transfer', 'pic_transfer', 'bukti_transfer']
        widgets = {
            'tanggal_transfer': forms.DateInput(attrs={'type': 'date'}),
            'bukti_transfer': forms.FileInput(attrs={'accept': 'image/*,.pdf'}),
            'pic_transfer': forms.TextInput(attrs={'placeholder': 'Nama petugas yang melakukan transfer'}),
        }

    def clean_bukti_transfer(self):
        bukti_transfer = self.cleaned_data.get('bukti_transfer')
        if not bukti_transfer and not self.instance.bukti_transfer:
            raise forms.ValidationError('Bukti screenshot transfer wajib diupload.')
        return bukti_transfer


class SuratHonorAslebGenerateForm(forms.Form):
    bulan = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'month'}),
        input_formats=['%Y-%m', '%Y-%m-%d'],
        help_text='Pilih bulan honor yang akan dibuatkan surat.',
    )
    nomor_surat = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={'placeholder': 'Contoh: 0363/AK.01.02/FTI-Kajur.TIF/VI/2026'}),
    )
    tanggal_surat = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    perihal = forms.CharField(
        max_length=200,
        initial=SuratHonorAsleb._meta.get_field('perihal').default,
        widget=forms.TextInput(attrs={'placeholder': 'Perihal surat'}),
    )

    def clean_bulan(self):
        bulan = self.cleaned_data['bulan']
        return bulan.replace(day=1)


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

    def clean_file_modul(self):
        file_modul = self.cleaned_data['file_modul']
        file_hash = hash_uploaded_file(file_modul)
        duplicate = AbsensiAsleb.objects.filter(file_modul_hash=file_hash)

        if self.instance and self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)

        if duplicate.exists():
            raise forms.ValidationError('Berkas modul ini sudah pernah diupload. Gunakan file modul yang berbeda.')

        self.cleaned_data['file_modul_hash'] = file_hash
        return file_modul

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.file_modul_hash = self.cleaned_data.get('file_modul_hash', instance.file_modul_hash)

        if commit:
            instance.save()

        return instance


def hash_uploaded_file(uploaded_file):
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()
