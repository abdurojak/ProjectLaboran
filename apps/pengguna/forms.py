from django import forms
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import OperationalError, ProgrammingError
from .models import Fakultas, PengalamanPengguna, Pengguna, Prodi, School
from .utils import validate_human_face_photo


def active_name_choices(model, empty_label):
    try:
        choices = list(model.objects.filter(aktif=True).values_list('nama', 'nama'))
    except (OperationalError, ProgrammingError):
        choices = []

    return [('', empty_label), *choices]


def apply_fakultas_prodi_choices(form):
    form.fields['fakultas'].widget = forms.Select(choices=active_name_choices(Fakultas, 'Pilih fakultas'))
    form.fields['prodi'].widget = forms.Select(choices=active_name_choices(Prodi, 'Pilih prodi'))


def add_password_validator_errors(form, password):
    if not password:
        return

    try:
        validate_password(password)
    except ValidationError as exc:
        form.add_error('password', exc)


class PenggunaForm(forms.ModelForm):
    class Meta:
        model = Pengguna
        fields = [
            'foto',
            'background_image',
            'nama_pengguna',
            'nim_nik',
            'email',
            'password',
            'gender',
            'no_hp',
            'alamat',
            'fakultas',
            'prodi',
            'ringkasan_profesional',
            'keahlian',
            'role',
            'is_verified',
        ]
        widgets = {
            'foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'background_image': forms.FileInput(attrs={'accept': 'image/*'}),
            'password': forms.PasswordInput(render_value=False),
            'alamat': forms.Textarea(attrs={'rows': 4}),
            'ringkasan_profesional': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Ceritakan profil, minat, dan tujuan profesional Anda.'}),
            'keahlian': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Contoh: Python, Django, Basis Data, Public Speaking'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_fakultas_prodi_choices(self)
        self.initial_password = self.instance.password
        if self.instance.pk:
            self.fields['password'].required = False
            self.fields['password'].help_text = 'Kosongkan jika tidak ingin mengganti password.'
        self.fields['is_verified'].help_text = 'Jika dinonaktifkan, pengguna tidak dapat login sampai akun diverifikasi kembali.'

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        validate_human_face_photo(foto)
        return foto

    def clean(self):
        cleaned_data = super().clean()
        add_password_validator_errors(self, cleaned_data.get('password'))
        return cleaned_data

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


class FakultasForm(forms.ModelForm):
    class Meta:
        model = Fakultas
        fields = ['nama', 'aktif']
        widgets = {
            'nama': forms.TextInput(attrs={'placeholder': 'Contoh: Teknologi Industri'}),
        }


class ProdiForm(forms.ModelForm):
    class Meta:
        model = Prodi
        fields = ['nama', 'aktif']
        widgets = {
            'nama': forms.TextInput(attrs={'placeholder': 'Contoh: Informatika'}),
        }


class PenggunaAppearanceForm(forms.ModelForm):
    hapus_background = forms.BooleanField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Pengguna
        fields = ['theme_mode', 'background_mode', 'background_image']
        widgets = {
            'theme_mode': forms.RadioSelect,
            'background_mode': forms.RadioSelect,
            'background_image': forms.FileInput(attrs={'accept': 'image/*'}),
        }

    def clean_background_image(self):
        image = self.cleaned_data.get('background_image')
        if image and image.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Ukuran gambar background maksimal 2 MB.')
        return image

    def save(self, commit=True):
        instance = super().save(commit=False)
        old_background = None
        if instance.pk:
            old_background = Pengguna.objects.filter(pk=instance.pk).values_list('background_image', flat=True).first()

        if self.cleaned_data.get('hapus_background'):
            instance.background_image = None
            if instance.background_mode == 'custom':
                instance.background_mode = 'default'
        elif self.cleaned_data.get('background_image'):
            instance.background_mode = 'custom'

        if instance.background_mode == 'custom' and not instance.background_image:
            instance.background_mode = 'default'

        if commit:
            instance.save(update_fields=['theme_mode', 'background_mode', 'background_image', 'diperbarui_pada'])
            new_background = instance.background_image.name if instance.background_image else ''
            if old_background and old_background != new_background:
                instance._meta.get_field('background_image').storage.delete(old_background)
        return instance


class PenggunaProfileForm(forms.ModelForm):
    class Meta:
        model = Pengguna
        fields = [
            'foto',
            'cover_image',
            'nama_pengguna',
            'nim_nik',
            'email',
            'gender',
            'no_hp',
            'alamat',
            'fakultas',
            'prodi',
            'ringkasan_profesional',
            'keahlian',
            'role',
        ]
        widgets = {
            'foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'cover_image': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'no_hp': forms.TextInput(attrs={'inputmode': 'numeric', 'pattern': '[0-9]*', 'placeholder': 'Angka saja'}),
            'alamat': forms.Textarea(attrs={'rows': 4}),
            'ringkasan_profesional': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Ceritakan profil, minat, dan tujuan profesional Anda.'}),
            'keahlian': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Contoh: Python, Django, Basis Data, Public Speaking'}),
        }

    def __init__(self, *args, **kwargs):
        self.current_pengguna = kwargs.pop('current_pengguna', None)
        super().__init__(*args, **kwargs)
        apply_fakultas_prodi_choices(self)
        if self.current_pengguna and self.current_pengguna.role != 'admin':
            self.fields.pop('role', None)

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        if not (self.current_pengguna and self.current_pengguna.role == 'admin'):
            validate_human_face_photo(foto)
        return foto

    def clean_no_hp(self):
        no_hp = self.cleaned_data.get('no_hp', '').strip()
        if no_hp and not no_hp.isdigit():
            raise forms.ValidationError('No HP hanya boleh berisi angka.')
        return no_hp

    def save(self, commit=True):
        instance = super().save(commit=False)
        hapus_foto = self.data.get('hapus_foto') == '1'

        if self.current_pengguna and self.current_pengguna.role != 'admin':
            instance.role = self.instance.role

        if hapus_foto:
            instance.foto = None

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class RiwayatProfilFormBase(forms.ModelForm):
    category = None

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('masih_berjalan'):
            cleaned_data['tanggal_selesai'] = None
            self.instance.tanggal_selesai = None
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.kategori = self.category
        if commit:
            instance.save()
            self.save_m2m()
        return instance

    class Meta:
        model = PengalamanPengguna
        fields = []
        widgets = {
            'tanggal_mulai': forms.DateInput(attrs={'type': 'date'}),
            'tanggal_selesai': forms.DateInput(attrs={'type': 'date'}),
            'deskripsi': forms.Textarea(attrs={'rows': 5}),
        }


class PengalamanPenggunaForm(RiwayatProfilFormBase):
    category = 'pengalaman'

    class Meta:
        model = PengalamanPengguna
        fields = ['jabatan', 'organisasi', 'lokasi', 'tanggal_mulai', 'tanggal_selesai', 'masih_berjalan', 'deskripsi']
        labels = {
            'jabatan': 'Posisi/Jabatan',
            'organisasi': 'Nama Instansi/Perusahaan',
            'masih_berjalan': 'Masih berjalan sampai sekarang',
            'deskripsi': 'Deskripsi pengalaman',
        }
        widgets = {
            'tanggal_mulai': forms.DateInput(attrs={'type': 'date'}),
            'tanggal_selesai': forms.DateInput(attrs={'type': 'date'}),
            'deskripsi': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Jelaskan tanggung jawab dan pencapaian Anda.'}),
        }


class PendidikanPenggunaForm(RiwayatProfilFormBase):
    category = 'pendidikan'
    JURUSAN_SMA = [
        ('', 'Pilih jurusan'),
        ('IPA', 'IPA'),
        ('IPS', 'IPS'),
        ('Bahasa', 'Bahasa'),
        ('Lainnya', 'Lainnya'),
    ]
    JURUSAN_SMK = [
        ('', 'Pilih jurusan'),
        ('Rekayasa Perangkat Lunak', 'Rekayasa Perangkat Lunak'),
        ('Teknik Komputer dan Jaringan', 'Teknik Komputer dan Jaringan'),
        ('Multimedia', 'Multimedia'),
        ('Akuntansi', 'Akuntansi'),
        ('Otomatisasi dan Tata Kelola Perkantoran', 'Otomatisasi dan Tata Kelola Perkantoran'),
        ('Jurusan lainnya', 'Jurusan lainnya'),
    ]
    jenjang_pendidikan = forms.ChoiceField(
        label='Jenjang Pendidikan',
        choices=[('', 'Pilih jenjang'), *School.LEVEL_CHOICES],
        required=True,
    )
    sekolah = forms.ModelChoiceField(
        label='Nama Sekolah',
        queryset=School.objects.none(),
        required=False,
        widget=forms.HiddenInput(attrs={'data-school-id': 'true'}),
    )
    nama_sekolah_manual = forms.CharField(
        label='Masukkan nama sekolah secara manual',
        max_length=180,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Contoh: SMA Harapan Bangsa'}),
    )
    bidang_studi = forms.CharField(
        label='Jurusan',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Pilih/isi jurusan'}),
    )

    class Meta:
        model = PengalamanPengguna
        fields = [
            'jenjang_pendidikan',
            'sekolah',
            'nama_sekolah_manual',
            'bidang_studi',
            'tanggal_mulai',
            'tanggal_selesai',
            'masih_berjalan',
            'nilai_akhir',
            'deskripsi',
        ]
        labels = {
            'bidang_studi': 'Jurusan/Program Studi',
            'tanggal_mulai': 'Tahun masuk',
            'tanggal_selesai': 'Tahun selesai',
            'masih_berjalan': 'Masih menempuh pendidikan',
            'nilai_akhir': 'Nilai akhir (opsional)',
            'deskripsi': 'Deskripsi tambahan',
        }
        widgets = {
            **RiwayatProfilFormBase.Meta.widgets,
            'tanggal_mulai': forms.DateInput(attrs={'type': 'date'}),
            'tanggal_selesai': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        selected_school = None
        if self.data:
            selected_school = self.data.get(self.add_prefix('sekolah')) or self.data.get('sekolah')
        if selected_school:
            self.fields['sekolah'].queryset = School.objects.filter(pk=selected_school, aktif=True)
        elif self.instance and self.instance.sekolah_id:
            self.fields['sekolah'].queryset = School.objects.filter(pk=self.instance.sekolah_id)
        else:
            self.fields['sekolah'].queryset = School.objects.none()
        self.fields['jenjang_pendidikan'].widget.attrs.update({'data-education-level': 'true'})
        self.fields['bidang_studi'].widget.attrs.update({'data-education-major': 'true', 'list': 'education-major-options'})
        self.fields['nama_sekolah_manual'].widget.attrs.update({'data-school-manual': 'true'})

    def clean(self):
        cleaned_data = super().clean()
        level = cleaned_data.get('jenjang_pendidikan')
        school = cleaned_data.get('sekolah')
        manual = (cleaned_data.get('nama_sekolah_manual') or '').strip()
        major = (cleaned_data.get('bidang_studi') or '').strip()
        start = cleaned_data.get('tanggal_mulai')
        end = cleaned_data.get('tanggal_selesai')
        still = cleaned_data.get('masih_berjalan')

        if school and manual:
            raise ValidationError('Pilih sekolah dari dropdown atau isi manual, jangan keduanya.')
        if not school and not manual:
            raise ValidationError('Pilih sekolah dari dropdown atau isi nama sekolah manual.')
        if school and level and school.jenjang != level:
            self.add_error('sekolah', 'Sekolah yang dipilih tidak sesuai jenjang.')
        if level in {'SMA', 'SMK'} and not major:
            self.add_error('bidang_studi', 'Jurusan wajib diisi untuk SMA/SMK.')
        if level in {'SD', 'SMP'}:
            cleaned_data['bidang_studi'] = ''
            self.instance.bidang_studi = ''
        if still:
            cleaned_data['tanggal_selesai'] = None
            self.instance.tanggal_selesai = None
        elif start and end and start > end:
            self.add_error('tanggal_selesai', 'Tahun selesai tidak boleh lebih awal dari tahun masuk.')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        school = self.cleaned_data.get('sekolah')
        manual = (self.cleaned_data.get('nama_sekolah_manual') or '').strip()
        instance.jenjang_pendidikan = self.cleaned_data.get('jenjang_pendidikan') or ''
        instance.sekolah = school
        instance.sekolah_npsn = school.npsn if school else ''
        instance.sekolah_snapshot = school.nama if school else ''
        instance.nama_sekolah_manual = manual if not school else ''
        instance.organisasi = school.nama if school else manual
        instance.jabatan = self.cleaned_data.get('bidang_studi') or instance.organisasi
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class OrganisasiPenggunaForm(RiwayatProfilFormBase):
    category = 'organisasi'

    class Meta:
        model = PengalamanPengguna
        fields = ['organisasi', 'jabatan', 'lokasi', 'tanggal_mulai', 'tanggal_selesai', 'masih_berjalan', 'deskripsi']
        labels = {
            'organisasi': 'Nama Organisasi',
            'jabatan': 'Jabatan/Posisi',
            'masih_berjalan': 'Masih aktif',
            'deskripsi': 'Kegiatan atau tanggung jawab',
        }
        widgets = RiwayatProfilFormBase.Meta.widgets


class ProyekPenggunaForm(RiwayatProfilFormBase):
    category = 'proyek'

    class Meta:
        model = PengalamanPengguna
        fields = ['jabatan', 'organisasi', 'teknologi', 'tautan', 'tanggal_mulai', 'tanggal_selesai', 'masih_berjalan', 'deskripsi']
        labels = {
            'jabatan': 'Nama Proyek',
            'organisasi': 'Peran dalam Proyek',
            'teknologi': 'Teknologi yang Digunakan',
            'tautan': 'Link Proyek (opsional)',
            'masih_berjalan': 'Masih dikerjakan',
            'deskripsi': 'Deskripsi proyek',
        }
        widgets = RiwayatProfilFormBase.Meta.widgets


class SertifikasiPenggunaForm(RiwayatProfilFormBase):
    category = 'sertifikasi'

    class Meta:
        model = PengalamanPengguna
        fields = ['jabatan', 'organisasi', 'tanggal_mulai', 'tanggal_selesai', 'masih_berjalan', 'nomor_kredensial', 'tautan', 'file_sertifikat']
        labels = {
            'jabatan': 'Nama Sertifikat',
            'organisasi': 'Penerbit/Instansi',
            'tanggal_mulai': 'Tanggal Terbit',
            'tanggal_selesai': 'Tanggal Kedaluwarsa',
            'masih_berjalan': 'Tidak ada tanggal kedaluwarsa',
            'nomor_kredensial': 'Nomor Kredensial (opsional)',
            'tautan': 'Link Kredensial (opsional)',
            'file_sertifikat': 'Upload File Sertifikat (opsional)',
        }
        widgets = RiwayatProfilFormBase.Meta.widgets


class ChangePasswordForm(forms.Form):
    password = forms.CharField(label='Password baru', widget=forms.PasswordInput)
    password_confirmation = forms.CharField(label='Konfirmasi password baru', widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirmation = cleaned_data.get('password_confirmation')

        if password and password_confirmation and password != password_confirmation:
            self.add_error('password_confirmation', 'Konfirmasi password tidak sama.')

        add_password_validator_errors(self, password)
        return cleaned_data


class LoginPenggunaForm(forms.Form):
    JENIS_LOGIN_CHOICES = [
        ('mahasiswa', 'Mahasiswa'),
        ('karyawan', 'Karyawan'),
    ]

    jenis_login = forms.ChoiceField(
        label='Masuk sebagai',
        choices=JENIS_LOGIN_CHOICES,
        initial='mahasiswa',
        required=False,
        widget=forms.RadioSelect,
    )
    nim_nik = forms.CharField(
        label='NIM atau NIK',
        max_length=40,
        widget=forms.TextInput(attrs={
            'autocomplete': 'username',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
            'placeholder': 'Masukkan NIM atau NIK',
        }),
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))

    error_messages = {
        'invalid_login': 'NIM/NIK atau password tidak sesuai.',
    }

    def clean_nim_nik(self):
        nim_nik = self.cleaned_data['nim_nik'].strip()
        if not nim_nik.isdigit():
            raise forms.ValidationError('NIM/NIK hanya boleh berisi angka.')
        return nim_nik

    def clean(self):
        cleaned_data = super().clean()
        jenis_login = cleaned_data.get('jenis_login') or 'mahasiswa'
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

        if jenis_login == 'mahasiswa' and pengguna.role not in ['mahasiswa', 'asisten_lab']:
            raise forms.ValidationError('Akun ini bukan akun mahasiswa. Pilih login sebagai karyawan.')

        if jenis_login == 'karyawan' and pengguna.role not in ['admin', 'laboran']:
            raise forms.ValidationError('Akun ini bukan akun karyawan. Pilih login sebagai mahasiswa.')

        cleaned_data['pengguna'] = pengguna
        return cleaned_data


class RegisterPenggunaForm(forms.ModelForm):
    # Registrasi menerima local-part saja; domain kampus ditambahkan di clean_email().
    email = forms.CharField(
        label='Email',
        widget=forms.TextInput(attrs={
            'autocomplete': 'email',
            'placeholder': 'nama.email',
            'pattern': '[A-Za-z0-9._%+-]+(@std\\.trisakti\\.ac\\.id)?',
            'title': 'Cukup isi nama email. Domain @std.trisakti.ac.id akan ditambahkan otomatis.',
        }),
    )
    password_confirmation = forms.CharField(label='Konfirmasi password', widget=forms.PasswordInput)

    class Meta:
        model = Pengguna
        fields = [
            'nama_pengguna',
            'nim_nik',
            'email',
            'password',
            'password_confirmation',
            'no_hp',
            'gender',
            'foto',
            'alamat',
            'fakultas',
            'prodi',
        ]
        labels = {
            'nim_nik': 'NIM',
        }
        widgets = {
            'foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'password': forms.PasswordInput(attrs={'autocomplete': 'new-password'}, render_value=False),
            'email': forms.TextInput(attrs={
                'autocomplete': 'email',
                'placeholder': 'nama.email',
                'pattern': '[A-Za-z0-9._%+-]+(@std\\.trisakti\\.ac\\.id)?',
                'title': 'Cukup isi nama email. Domain @std.trisakti.ac.id akan ditambahkan otomatis.',
            }),
            'nim_nik': forms.TextInput(attrs={
                'autocomplete': 'username',
                'inputmode': 'numeric',
                'minlength': '10',
                'pattern': '[0-9]{10,}',
                'placeholder': 'Minimal 10 digit',
                'title': 'NIM harus berisi minimal 10 digit angka',
            }),
            'no_hp': forms.TextInput(attrs={
                'autocomplete': 'tel',
                'inputmode': 'numeric',
                'pattern': '[0-9]*',
                'placeholder': 'Angka saja',
            }),
            'alamat': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_fakultas_prodi_choices(self)
        self.fields['foto'].required = True
        self.fields['foto'].help_text = 'Wajib unggah foto wajah asli untuk verifikasi akun.'
        self.fields['foto'].error_messages['required'] = (
            'Foto wajah wajib diunggah untuk melakukan registrasi.'
        )

    def clean_nim_nik(self):
        nim_nik = self.cleaned_data['nim_nik'].strip()
        if not nim_nik.isdigit():
            raise forms.ValidationError('NIM hanya boleh berisi angka.')
        if len(nim_nik) < 10:
            raise forms.ValidationError('NIM harus terdiri dari minimal 10 digit.')
        return nim_nik

    def clean_email(self):
        raw_email = self.cleaned_data['email'].strip().lower()
        if '@' in raw_email and not raw_email.endswith('@std.trisakti.ac.id'):
            raise forms.ValidationError('Email registrasi hanya boleh memakai domain @std.trisakti.ac.id.')
        local_part = raw_email.removesuffix('@std.trisakti.ac.id').strip()
        if not local_part:
            raise forms.ValidationError('Nama email wajib diisi.')
        if '@' in local_part:
            raise forms.ValidationError('Cukup isi nama email tanpa domain.')
        email = f'{local_part}@std.trisakti.ac.id'
        if Pengguna.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Email sudah terdaftar. Gunakan email Trisakti lain atau login.')
        return email

    def clean_no_hp(self):
        no_hp = self.cleaned_data.get('no_hp', '').strip()
        if no_hp and not no_hp.isdigit():
            raise forms.ValidationError('No HP hanya boleh berisi angka.')
        return no_hp

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        if not foto:
            raise forms.ValidationError('Foto wajah wajib diunggah untuk melakukan registrasi.')
        validate_human_face_photo(foto)
        return foto

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirmation = cleaned_data.get('password_confirmation')

        if password and password_confirmation and password != password_confirmation:
            self.add_error('password_confirmation', 'Konfirmasi password tidak sama.')

        add_password_validator_errors(self, password)
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.role = 'mahasiswa'
        instance.is_verified = False

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
    nim_nik = forms.CharField(label='NIM/NIK', max_length=40, widget=forms.TextInput(attrs={
        'inputmode': 'numeric',
        'pattern': '[0-9]*',
    }))

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

        add_password_validator_errors(self, password)
        return cleaned_data
