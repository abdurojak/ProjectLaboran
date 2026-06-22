from django import forms
from django.contrib.auth.hashers import check_password

from .models import Pengguna


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
            'no_hp',
            'alamat',
            'fakultas',
            'prodi',
        ]
        widgets = {
            'foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'password': forms.PasswordInput(render_value=False),
            'alamat': forms.Textarea(attrs={'rows': 4}),
        }

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

        if commit:
            instance.save()
            self.save_m2m()

        return instance
