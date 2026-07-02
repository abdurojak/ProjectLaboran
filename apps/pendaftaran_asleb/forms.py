import base64
import binascii
import uuid

from django import forms
from django.core.files.base import ContentFile

from .models import MataKuliahAsleb, PendaftaranAsleb, PengaturanBiayaTransfer, PeriodeAsleb
from .utils import extract_grade_from_transcript, is_passing_grade


class PendaftaranAslebForm(forms.ModelForm):
    SEMESTER_CHOICES = [(semester, f'Semester {semester}') for semester in range(3, 9)]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['matkul'].queryset = MataKuliahAsleb.objects.filter(aktif=True)
        self.fields['matkul'].empty_label = 'Pilih mata kuliah'
        self.fields['semester'].widget = forms.Select(choices=self.SEMESTER_CHOICES)

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
            'transkrip',
            'tanda_tangan',
            'metode_rekening',
            'rekening',
            'nama_pemilik_rekening',
            'nilai_transkrip',
            'alasan',
            'status',
        ]
        widgets = {
            'nama': forms.TextInput(attrs={'placeholder': 'Nama lengkap calon aslab'}),
            'nim': forms.TextInput(attrs={'placeholder': 'NIM mahasiswa'}),
            'no_hp': forms.TextInput(attrs={'placeholder': 'Nomor HP aktif'}),
            'program_studi': forms.TextInput(attrs={'placeholder': 'Contoh: Rekayasa Perangkat Lunak'}),
            'matkul': forms.Select(attrs={'class': 'min-h-12'}),
            'tanda_tangan': forms.FileInput(attrs={'accept': 'image/*'}),
            'rekening': forms.TextInput(attrs={'placeholder': 'Nomor rekening atau e-wallet'}),
            'nama_pemilik_rekening': forms.TextInput(attrs={'placeholder': 'Nama pemilik rekening/e-wallet'}),
            'alasan': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Alasan atau catatan pendaftaran'}),
        }

    def clean_semester(self):
        semester = self.cleaned_data['semester']
        if semester < 3 or semester > 8:
            raise forms.ValidationError('Semester hanya boleh 3 sampai 8.')
        return semester

    def clean(self):
        cleaned_data = super().clean()
        validate_payment_account(self, cleaned_data)
        transcript = cleaned_data.get('transkrip') or getattr(self.instance, 'transkrip', None)
        detected_grade = extract_grade_from_transcript(transcript, cleaned_data.get('matkul'))

        if detected_grade:
            cleaned_data['nilai_transkrip'] = detected_grade
        elif not cleaned_data.get('nilai_transkrip'):
            cleaned_data['nilai_transkrip'] = 'tidak_terbaca'

        cleaned_data['skor_nilai'] = PendaftaranAsleb.grade_to_score(cleaned_data['nilai_transkrip'])
        if cleaned_data['nilai_transkrip'] != 'tidak_terbaca' and not is_passing_grade(cleaned_data['nilai_transkrip']):
            self.add_error('transkrip', 'Nilai mata kuliah minimal B untuk mendaftar sebagai aslab.')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.periode_id:
            from .services import get_current_period
            instance.periode = get_current_period()
        detected_grade = self.cleaned_data.get('nilai_transkrip') or instance.nilai_transkrip
        instance.nilai_transkrip = detected_grade
        instance.skor_nilai = PendaftaranAsleb.grade_to_score(detected_grade)

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class PendaftaranAslebPublicForm(PendaftaranAslebForm):
    signature_data = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        self.current_pengguna = kwargs.pop('current_pengguna', None)
        super().__init__(*args, **kwargs)
        if self.current_pengguna and self.current_pengguna.role in ['mahasiswa', 'asisten_lab']:
            self.fields['nama'].initial = self.current_pengguna.nama_pengguna
            self.fields['nim'].initial = self.current_pengguna.nim_nik
            self.fields['no_hp'].initial = self.current_pengguna.no_hp
            self.fields['email'].initial = self.current_pengguna.email
            self.fields['program_studi'].initial = self.current_pengguna.prodi

            for field_name in ['nama', 'nim', 'no_hp', 'email', 'program_studi']:
                self.fields[field_name].required = False
                self.fields[field_name].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        if self.current_pengguna and self.current_pengguna.role in ['mahasiswa', 'asisten_lab']:
            cleaned_data['nama'] = self.current_pengguna.nama_pengguna
            cleaned_data['nim'] = self.current_pengguna.nim_nik
            cleaned_data['no_hp'] = self.current_pengguna.no_hp
            cleaned_data['email'] = self.current_pengguna.email
            cleaned_data['program_studi'] = self.current_pengguna.prodi
        return cleaned_data

    def clean_signature_data(self):
        signature_data = self.cleaned_data.get('signature_data')
        decode_signature_data(signature_data)
        return signature_data

    class Meta(PendaftaranAslebForm.Meta):
        fields = [
            'nama',
            'nim',
            'no_hp',
            'email',
            'program_studi',
            'semester',
            'matkul',
            'transkrip',
            'metode_rekening',
            'rekening',
            'alasan',
            'signature_data',
        ]

    def save(self, commit=True):
        instance = super().save(commit=False)
        signature_file = decode_signature_data(self.cleaned_data.get('signature_data'))

        if self.current_pengguna:
            instance.nama = self.current_pengguna.nama_pengguna
            instance.nim = self.current_pengguna.nim_nik
            instance.no_hp = self.current_pengguna.no_hp
            instance.email = self.current_pengguna.email
            instance.program_studi = self.current_pengguna.prodi

        if signature_file:
            instance.tanda_tangan = signature_file

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class PublicPilihMatkulForm(forms.Form):
    matkul = forms.ModelChoiceField(
        queryset=MataKuliahAsleb.objects.none(),
        empty_label='Pilih mata kuliah',
        widget=forms.Select(attrs={'class': 'min-h-12'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['matkul'].queryset = MataKuliahAsleb.objects.filter(aktif=True)


class PublicTranskripForm(forms.Form):
    transkrip = forms.FileField(
        label='Upload Transkrip Nilai',
        widget=forms.FileInput(attrs={'accept': '.pdf,.png,.jpg,.jpeg,.webp,.txt,.csv'}),
        help_text='Gunakan file PDF agar hasil pembacaan paling akurat. Sistem mencocokkan NIM dan memastikan nilai mata kuliah minimal B.',
    )


class PublicBerkasPendaftaranForm(forms.Form):
    SEMESTER_CHOICES = [(semester, f'Semester {semester}') for semester in range(3, 9)]
    signature_data = forms.CharField(widget=forms.HiddenInput, required=False)
    pernyataan_data = forms.BooleanField(
        required=True,
        error_messages={'required': 'Anda harus menyetujui pernyataan kebenaran data sebelum mengirim pendaftaran.'},
    )

    nama = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'placeholder': 'Nama lengkap calon aslab'}))
    nim = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'placeholder': 'NIM mahasiswa'}))
    no_hp = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'placeholder': 'Nomor HP aktif'}))
    email = forms.EmailField(required=False)
    program_studi = forms.CharField(max_length=120, widget=forms.TextInput(attrs={'placeholder': 'Program studi'}))
    semester = forms.ChoiceField(choices=SEMESTER_CHOICES)
    metode_rekening = forms.ChoiceField(choices=PendaftaranAsleb.METODE_REKENING_CHOICES)
    rekening = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'placeholder': 'Masukkan nomor rekening atau nomor e-wallet'}))
    nama_pemilik_rekening = forms.CharField(
        label='Atas Nama',
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Nama pemilik rekening atau e-wallet'}),
    )
    alasan = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Alasan atau catatan pendaftaran'}))

    def __init__(self, *args, **kwargs):
        self.current_pengguna = kwargs.pop('current_pengguna', None)
        super().__init__(*args, **kwargs)
        if self.current_pengguna and self.current_pengguna.role in ['mahasiswa', 'asisten_lab']:
            self.fields['nama'].initial = self.current_pengguna.nama_pengguna
            self.fields['nim'].initial = self.current_pengguna.nim_nik
            self.fields['no_hp'].initial = self.current_pengguna.no_hp
            self.fields['email'].initial = self.current_pengguna.email
            self.fields['program_studi'].initial = self.current_pengguna.prodi

            for field_name in ['nama', 'nim', 'no_hp', 'email', 'program_studi']:
                self.fields[field_name].required = False
                self.fields[field_name].widget = forms.HiddenInput()

    def clean_semester(self):
        semester = int(self.cleaned_data['semester'])
        if semester < 3 or semester > 8:
            raise forms.ValidationError('Semester hanya boleh 3 sampai 8.')
        return semester

    def clean_signature_data(self):
        signature_data = self.cleaned_data.get('signature_data')
        decode_signature_data(signature_data)
        return signature_data

    def clean(self):
        cleaned_data = super().clean()
        validate_payment_account(self, cleaned_data)
        if self.current_pengguna and self.current_pengguna.role in ['mahasiswa', 'asisten_lab']:
            cleaned_data['nama'] = self.current_pengguna.nama_pengguna
            cleaned_data['nim'] = self.current_pengguna.nim_nik
            cleaned_data['no_hp'] = self.current_pengguna.no_hp
            cleaned_data['email'] = self.current_pengguna.email
            cleaned_data['program_studi'] = self.current_pengguna.prodi
        return cleaned_data


class RekeningPendaftaranForm(forms.ModelForm):
    class Meta:
        model = PendaftaranAsleb
        fields = ['metode_rekening', 'rekening', 'nama_pemilik_rekening']
        widgets = {
            'rekening': forms.TextInput(attrs={'placeholder': 'Nomor rekening atau e-wallet'}),
            'nama_pemilik_rekening': forms.TextInput(attrs={'placeholder': 'Nama pemilik rekening atau e-wallet'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        validate_payment_account(self, cleaned_data)
        return cleaned_data


class PengaturanBiayaTransferForm(forms.ModelForm):
    class Meta:
        model = PengaturanBiayaTransfer
        fields = [
            'biaya_bni', 'biaya_bank_lain', 'biaya_dana',
            'biaya_shopeepay', 'biaya_gopay', 'biaya_ovo',
        ]
        widgets = {
            'biaya_bni': forms.NumberInput(attrs={'min': 0, 'step': 500}),
            'biaya_bank_lain': forms.NumberInput(attrs={'min': 0, 'step': 500}),
            'biaya_dana': forms.NumberInput(attrs={'min': 0, 'step': 500}),
            'biaya_shopeepay': forms.NumberInput(attrs={'min': 0, 'step': 500}),
            'biaya_gopay': forms.NumberInput(attrs={'min': 0, 'step': 500}),
            'biaya_ovo': forms.NumberInput(attrs={'min': 0, 'step': 500}),
        }


def validate_payment_account(form, cleaned_data):
    method = cleaned_data.get('metode_rekening')
    account = (cleaned_data.get('rekening') or '').strip()
    owner = (cleaned_data.get('nama_pemilik_rekening') or '').strip()
    if method == 'bni' and account and not account.isdigit():
        form.add_error('rekening', 'Nomor rekening BNI hanya boleh berisi angka.')
    elif method == 'bank_lain' and account:
        if not any(char.isalpha() for char in account) or not any(char.isdigit() for char in account):
            form.add_error('rekening', 'Tulis nama bank dan nomor rekening, contoh: BCA 1234567890.')
    elif method in {'dana', 'shopeepay', 'gopay', 'ovo'} and account and not account.isdigit():
        form.add_error('rekening', 'Nomor e-wallet hanya boleh berisi angka.')
    if 'nama_pemilik_rekening' in form.fields and not owner:
        form.add_error('nama_pemilik_rekening', 'Nama pemilik rekening atau e-wallet wajib diisi.')


class PeriodeAslebForm(forms.ModelForm):
    class Meta:
        model = PeriodeAsleb
        fields = ['pendaftaran_mulai', 'pendaftaran_selesai']
        widgets = {
            'pendaftaran_mulai': forms.DateInput(attrs={'type': 'date'}),
            'pendaftaran_selesai': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('pendaftaran_mulai')
        end = cleaned_data.get('pendaftaran_selesai')
        if start and end and start > end:
            self.add_error('pendaftaran_selesai', 'Tanggal tutup harus setelah tanggal buka.')
        if start and (start < self.instance.mulai or start > self.instance.selesai):
            self.add_error('pendaftaran_mulai', 'Tanggal buka harus berada dalam periode aslab.')
        if end and (end < self.instance.mulai or end > self.instance.selesai):
            self.add_error('pendaftaran_selesai', 'Tanggal tutup harus berada dalam periode aslab.')
        return cleaned_data


class AkhiriPeriodeAslebForm(forms.Form):
    password = forms.CharField(
        label='Verifikasi Password Super Admin',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Masukkan password akun Anda',
            'autocomplete': 'current-password',
        }),
    )
    konfirmasi = forms.BooleanField(
        required=True,
        label='Saya memahami seluruh Asisten Lab pada periode ini akan dikembalikan menjadi Mahasiswa.',
    )


class MataKuliahAslebForm(forms.ModelForm):
    class Meta:
        model = MataKuliahAsleb
        fields = ['kode', 'kode_mk', 'nama', 'sks', 'dosen', 'kelas', 'aktif']
        widgets = {
            'kode': forms.TextInput(attrs={'placeholder': 'Contoh: PW_TIF01_NAMA'}),
            'kode_mk': forms.TextInput(attrs={'placeholder': 'Contoh: IKS6316'}),
            'nama': forms.TextInput(attrs={'placeholder': 'Nama mata kuliah'}),
            'sks': forms.NumberInput(attrs={'min': 0, 'placeholder': 'Contoh: 3'}),
            'dosen': forms.TextInput(attrs={'placeholder': 'Nama dosen'}),
            'kelas': forms.TextInput(attrs={'placeholder': 'Contoh: TIF-01'}),
        }


def decode_signature_data(signature_data):
    if not signature_data:
        raise forms.ValidationError('Tanda tangan wajib diisi.')

    header = 'data:image/png;base64,'
    if not signature_data.startswith(header):
        raise forms.ValidationError('Format tanda tangan tidak valid.')

    try:
        signature_bytes = base64.b64decode(signature_data[len(header):])
    except (binascii.Error, ValueError) as exc:
        raise forms.ValidationError('Tanda tangan tidak bisa diproses.') from exc

    if len(signature_bytes) < 500:
        raise forms.ValidationError('Tanda tangan terlalu kosong. Silakan tanda tangani ulang.')

    filename = f'tanda-tangan-{uuid.uuid4().hex}.png'
    return ContentFile(signature_bytes, name=filename)
