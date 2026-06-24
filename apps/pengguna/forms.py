from django import forms
from django.contrib.auth.hashers import check_password

from .models import Pengguna


FAKULTAS_CHOICES = [
    ('', 'Pilih fakultas'),
    ('Teknologi Industri', 'Teknologi Industri'),
    ('Ekonomi', 'Ekonomi'),
    ('Teknologi Kebumian dan Energi', 'Teknologi Kebumian dan Energi'),
    ('Arsitektur Lanskap dan Teknologi Lingkungan', 'Arsitektur Lanskap dan Teknologi Lingkungan'),
    ('Teknik Sipil dan Perencanaan', 'Teknik Sipil dan Perencanaan'),
    ('Kedokteran Gigi', 'Kedokteran Gigi'),
    ('Kedokteran', 'Kedokteran'),
    ('Hukum', 'Hukum'),
    ('Seni Rupa dan Desain', 'Seni Rupa dan Desain'),
]

PRODI_CHOICES = [
    ('', 'Pilih prodi'),
    ('Informatika', 'Informatika'),
    ('Sistem Informasi', 'Sistem Informasi'),
    ('Rekayasa Perangkat Lunak', 'Rekayasa Perangkat Lunak'),
    ('Sistem Keamanan Informasi', 'Sistem Keamanan Informasi'),
    ('Rekayasa Data', 'Rekayasa Data'),
    ('Manajemen', 'Manajemen'),
    ('Akuntansi', 'Akuntansi'),
    ('Teknik Industri', 'Teknik Industri'),
    ('Teknik Elektro', 'Teknik Elektro'),
    ('Teknik Mesin', 'Teknik Mesin'),
    ('Teknik Sipil', 'Teknik Sipil'),
]


def apply_fakultas_prodi_choices(form):
    form.fields['fakultas'].widget = forms.Select(choices=FAKULTAS_CHOICES)
    form.fields['prodi'].widget = forms.Select(choices=PRODI_CHOICES)


class PenggunaForm(forms.ModelForm):
    class Meta:
        model = Pengguna
        fields = [
            'foto',
            'nama_pengguna',
            'nim_nik',
            'email',
            'password',
            'gender',
            'no_hp',
            'alamat',
            'fakultas',
            'prodi',
            'role',
        ]
        widgets = {
            'foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'password': forms.PasswordInput(render_value=False),
            'alamat': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_fakultas_prodi_choices(self)
        self.initial_password = self.instance.password
        if self.instance.pk:
            self.fields['password'].required = False
            self.fields['password'].help_text = 'Kosongkan jika tidak ingin mengganti password.'

    def save(self, commit=True):
        instance = super().save(commit=False)
        password = self.cleaned_data.get('password')
        hapus_foto = self.data.get('hapus_foto') == '1'

        if self.instance.pk and not password:
            instance.password = self.initial_password

        if hapus_foto:
            instance.foto = None

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class PenggunaProfileForm(forms.ModelForm):
    class Meta:
        model = Pengguna
        fields = [
            'foto',
            'nama_pengguna',
            'nim_nik',
            'email',
            'gender',
            'no_hp',
            'alamat',
            'fakultas',
            'prodi',
            'role',
        ]
        widgets = {
            'foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'alamat': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        self.current_pengguna = kwargs.pop('current_pengguna', None)
        super().__init__(*args, **kwargs)
        apply_fakultas_prodi_choices(self)
        if self.current_pengguna and self.current_pengguna.role == 'mahasiswa':
            self.fields.pop('role', None)

    def save(self, commit=True):
        instance = super().save(commit=False)
        hapus_foto = self.data.get('hapus_foto') == '1'

        if self.current_pengguna and self.current_pengguna.role == 'mahasiswa':
            instance.role = self.instance.role

        if hapus_foto:
            instance.foto = None

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class ChangePasswordForm(forms.Form):
    password = forms.CharField(label='Password baru', widget=forms.PasswordInput)
    password_confirmation = forms.CharField(label='Konfirmasi password baru', widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirmation = cleaned_data.get('password_confirmation')

        if password and password_confirmation and password != password_confirmation:
            self.add_error('password_confirmation', 'Konfirmasi password tidak sama.')

        return cleaned_data


class LoginPenggunaForm(forms.Form):
    nim_nik = forms.CharField(label='NIM/NIK', max_length=40)
    password = forms.CharField(widget=forms.PasswordInput)

    error_messages = {
        'invalid_login': 'NIM/NIK atau password tidak sesuai.',
    }

    def clean(self):
        cleaned_data = super().clean()
        nim_nik = cleaned_data.get('nim_nik')
        password = cleaned_data.get('password')

        if not nim_nik or not password:
            return cleaned_data

        try:
            pengguna = Pengguna.objects.get(nim_nik=nim_nik)
        except Pengguna.DoesNotExist:
            raise forms.ValidationError(self.error_messages['invalid_login'])

        if not pengguna.is_verified:
            raise forms.ValidationError('Akun belum diverifikasi. Selesaikan verifikasi terlebih dahulu.')

        if not check_password(password, pengguna.password):
            raise forms.ValidationError(self.error_messages['invalid_login'])

        cleaned_data['pengguna'] = pengguna
        return cleaned_data


class RegisterPenggunaForm(forms.ModelForm):
    password_confirmation = forms.CharField(label='Konfirmasi password', widget=forms.PasswordInput)

    class Meta:
        model = Pengguna
        fields = [
            'foto',
            'nama_pengguna',
            'nim_nik',
            'email',
            'password',
            'password_confirmation',
            'gender',
            'alamat',
            'fakultas',
            'prodi',
        ]
        widgets = {
            'foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'password': forms.PasswordInput(render_value=False),
            'email': forms.EmailInput(attrs={
                'placeholder': 'nama@std.trisakti.ac.id atau nama@trisakti.ac.id',
                'pattern': '.+@(std\\.trisakti\\.ac\\.id|trisakti\\.ac\\.id)',
                'title': 'Gunakan email dengan akhiran @std.trisakti.ac.id atau @trisakti.ac.id',
            }),
            'nim_nik': forms.TextInput(attrs={'inputmode': 'numeric', 'pattern': '[0-9]*', 'placeholder': 'Angka saja'}),
            'alamat': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_fakultas_prodi_choices(self)

    def clean_nim_nik(self):
        nim_nik = self.cleaned_data['nim_nik'].strip()
        if not nim_nik.isdigit():
            raise forms.ValidationError('NIM/NIK hanya boleh berisi angka.')
        return nim_nik

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        valid_domains = ('@std.trisakti.ac.id', '@trisakti.ac.id')
        if not email.endswith(valid_domains):
            raise forms.ValidationError('Email harus menggunakan domain @std.trisakti.ac.id atau @trisakti.ac.id.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirmation = cleaned_data.get('password_confirmation')

        if password and password_confirmation and password != password_confirmation:
            self.add_error('password_confirmation', 'Konfirmasi password tidak sama.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.role = 'mahasiswa'
        instance.is_verified = False
        instance.no_hp = ''

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class VerificationCodeForm(forms.Form):
    kode = forms.CharField(
        label='Kode verifikasi',
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'pattern': '[0-9]*', 'autocomplete': 'one-time-code'}),
    )

    def clean_kode(self):
        kode = self.cleaned_data['kode'].strip()
        if not kode.isdigit():
            raise forms.ValidationError('Kode verifikasi hanya boleh angka.')
        return kode


class ForgotPasswordRequestForm(forms.Form):
    VERIFICATION_METHOD_CHOICES = [
        ('email', 'Email Trisakti'),
        ('no_hp', 'No HP'),
    ]

    nim_nik = forms.CharField(label='NIM/NIK', max_length=40, widget=forms.TextInput(attrs={
        'inputmode': 'numeric',
        'pattern': '[0-9]*',
    }))
    verification_method = forms.ChoiceField(
        label='Kirim kode lewat',
        choices=VERIFICATION_METHOD_CHOICES,
        widget=forms.RadioSelect,
    )

    def clean_nim_nik(self):
        nim_nik = self.cleaned_data['nim_nik'].strip()
        if not nim_nik.isdigit():
            raise forms.ValidationError('NIM/NIK hanya boleh berisi angka.')
        return nim_nik


class ResetPasswordForm(VerificationCodeForm):
    password = forms.CharField(label='Password baru', widget=forms.PasswordInput)
    password_confirmation = forms.CharField(label='Konfirmasi password baru', widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirmation = cleaned_data.get('password_confirmation')

        if password and password_confirmation and password != password_confirmation:
            self.add_error('password_confirmation', 'Konfirmasi password tidak sama.')

        return cleaned_data
