from django import forms

from apps.pengguna.models import Pengguna

from .models import AbsensiAsleb, Asleb, HonorAsleb, ModulPraktikum, SuratHonorAsleb


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
            'nama': forms.TextInput(attrs={'placeholder': 'Nama lengkap aslab'}),
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
    modul_praktikum = forms.ModelChoiceField(
        label='Modul Praktikum',
        queryset=ModulPraktikum.objects.none(),
        empty_label='Pilih modul yang belum diabsen',
    )

    class Meta:
        model = AbsensiAsleb
        fields = [
            'tanggal_praktikum',
            'modul_praktikum',
            'pekerjaan',
            'bukti_video',
        ]
        widgets = {
            'tanggal_praktikum': forms.DateInput(attrs={'type': 'date'}),
            'pekerjaan': forms.Textarea(attrs={'rows': 4}),
            'bukti_video': forms.FileInput(attrs={'accept': 'video/*'}),
        }

    def __init__(self, *args, **kwargs):
        self.asleb = kwargs.pop('asleb')
        super().__init__(*args, **kwargs)
        matkul = get_asleb_matkul(self.asleb)
        used_modules = AbsensiAsleb.objects.filter(
            asleb=self.asleb,
            modul_praktikum__isnull=False,
        ).values_list('modul_praktikum_id', flat=True)
        queryset = ModulPraktikum.objects.none()
        if matkul:
            queryset = ModulPraktikum.objects.filter(matkul=matkul).exclude(pk__in=used_modules)
        self.fields['modul_praktikum'].queryset = queryset

    def clean_modul_praktikum(self):
        modul = self.cleaned_data['modul_praktikum']
        if AbsensiAsleb.objects.filter(asleb=self.asleb, modul_praktikum=modul).exists():
            raise forms.ValidationError('Modul ini sudah pernah diabsen dan tidak dapat dipilih lagi.')
        return modul

    def save(self, commit=True):
        instance = super().save(commit=False)
        modul = self.cleaned_data['modul_praktikum']
        instance.modul = modul.nomor
        instance.materi_praktikum = modul.judul
        instance.file_modul.name = modul.file.name

        if commit:
            instance.save()

        return instance


class ModulPraktikumForm(forms.ModelForm):
    class Meta:
        model = ModulPraktikum
        fields = ['matkul', 'nomor', 'judul', 'file']
        widgets = {
            'nomor': forms.NumberInput(attrs={'min': 1}),
            'judul': forms.TextInput(attrs={'placeholder': 'Judul atau materi modul'}),
            'file': forms.FileInput(attrs={'accept': '.pdf,.doc,.docx,.ppt,.pptx,.zip'}),
        }


def get_asleb_matkul(asleb):
    from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb

    registration = PendaftaranAsleb.objects.filter(
        nim=asleb.nim,
        status__in=['diterima', 'digenerate'],
    ).select_related('matkul').order_by('-pk').first()
    if registration:
        return registration.matkul
    return next((matkul for matkul in MataKuliahAsleb.objects.filter(aktif=True) if str(matkul) == asleb.matkul), None)
