from django import forms
from django.conf import settings
from django.utils import timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import asin, cos, radians, sin, sqrt

from apps.pengguna.models import Pengguna

from .models import (
    AbsensiAsleb,
    Asleb,
    HasilPraktikumMahasiswa,
    HonorAsleb,
    ModulPraktikum,
    SuratHonorAsleb,
)


ENABLE_CAMERA_LOCATION_CAPTURE = False


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
    latitude = forms.CharField(required=False, widget=forms.HiddenInput)
    longitude = forms.CharField(required=False, widget=forms.HiddenInput)
    gps_accuracy = forms.CharField(required=False, widget=forms.HiddenInput)
    modul_praktikum = forms.ModelChoiceField(
        label='Modul Praktikum',
        queryset=ModulPraktikum.objects.none(),
        empty_label='Pilih modul yang belum diabsen',
    )

    class Meta:
        model = AbsensiAsleb
        fields = [
            'modul_praktikum',
            'pekerjaan',
            'bukti_foto',
            'bukti_video',
            'latitude',
            'longitude',
            'gps_accuracy',
        ]
        widgets = {
            'pekerjaan': forms.Textarea(attrs={'rows': 4}),
            'bukti_foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/jpeg'}),
            'bukti_video': forms.FileInput(attrs={'class': 'hidden', 'accept': 'video/webm,video/mp4'}),
        }

    def __init__(self, *args, **kwargs):
        self.asleb = kwargs.pop('asleb')
        self.jadwal = kwargs.pop('jadwal')
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
        self.fields['bukti_foto'].required = ENABLE_CAMERA_LOCATION_CAPTURE
        self.fields['bukti_video'].required = ENABLE_CAMERA_LOCATION_CAPTURE

    def clean_bukti_foto(self):
        photo = self.cleaned_data['bukti_foto']
        if not photo and not ENABLE_CAMERA_LOCATION_CAPTURE:
            return photo
        if not self._has_allowed_content_type(photo, ['image/jpeg', 'image/png']):
            raise forms.ValidationError('Bukti foto harus diambil dari kamera dalam format gambar.')
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Ukuran bukti foto maksimal 5 MB.')
        return photo

    def clean_bukti_video(self):
        video = self.cleaned_data['bukti_video']
        if not video and not ENABLE_CAMERA_LOCATION_CAPTURE:
            return video
        if not self._has_allowed_content_type(video, ['video/webm', 'video/mp4']):
            raise forms.ValidationError('Bukti video harus direkam langsung dari kamera.')
        if video.size > 20 * 1024 * 1024:
            raise forms.ValidationError('Ukuran bukti video maksimal 20 MB.')
        return video

    def clean_modul_praktikum(self):
        modul = self.cleaned_data['modul_praktikum']
        if modul.matkul != get_asleb_matkul(self.asleb) or self.jadwal.mata_kuliah != str(modul.matkul):
            raise forms.ValidationError('Modul tidak sesuai dengan mata kuliah pada jadwal aktif.')
        if AbsensiAsleb.objects.filter(asleb=self.asleb, modul_praktikum=modul).exists():
            raise forms.ValidationError('Modul ini sudah pernah diabsen dan tidak dapat dipilih lagi.')
        return modul

    def clean(self):
        cleaned_data = super().clean()
        attendance_date = timezone.localdate()
        latitude = self._read_decimal(cleaned_data.get('latitude'))
        longitude = self._read_decimal(cleaned_data.get('longitude'))
        accuracy = self._read_float(cleaned_data.get('gps_accuracy'))

        if self.asleb and AbsensiAsleb.objects.filter(
            asleb=self.asleb,
            tanggal_praktikum=attendance_date,
        ).exists():
            raise forms.ValidationError(
                'Anda sudah melakukan absensi untuk jadwal praktikum hari ini. '
                'Perubahan jadwal tidak membuka absensi baru pada tanggal yang sama.'
            )

        if not ENABLE_CAMERA_LOCATION_CAPTURE:
            cleaned_data['latitude'] = None
            cleaned_data['longitude'] = None
            cleaned_data['distance_meters'] = None
            return cleaned_data

        if latitude is None or longitude is None or accuracy is None:
            raise forms.ValidationError('Lokasi perangkat wajib diaktifkan untuk melakukan absensi.')

        latitude = latitude.quantize(Decimal('0.0000001'), rounding=ROUND_HALF_UP)
        longitude = longitude.quantize(Decimal('0.0000001'), rounding=ROUND_HALF_UP)
        cleaned_data['latitude'] = latitude
        cleaned_data['longitude'] = longitude

        if accuracy > settings.ABSENSI_MAX_GPS_ACCURACY_METERS:
            raise forms.ValidationError('Akurasi lokasi belum cukup baik. Aktifkan GPS dan coba kembali di area terbuka.')

        distance = calculate_distance_meters(
            latitude,
            longitude,
            settings.ABSENSI_CENTER_LATITUDE,
            settings.ABSENSI_CENTER_LONGITUDE,
        )
        if distance > settings.ABSENSI_RADIUS_METERS:
            raise forms.ValidationError(
                f'Anda berada sekitar {round(distance)} meter dari lokasi praktikum. '
                f'Absensi hanya dapat dilakukan dalam radius {settings.ABSENSI_RADIUS_METERS} meter.'
            )
        cleaned_data['distance_meters'] = round(distance)
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        modul = self.cleaned_data['modul_praktikum']
        instance.jadwal = self.jadwal
        instance.tanggal_praktikum = timezone.localdate()
        instance.modul = modul.nomor
        instance.materi_praktikum = modul.judul
        instance.file_modul.name = modul.file.name
        instance.latitude = self.cleaned_data.get('latitude')
        instance.longitude = self.cleaned_data.get('longitude')
        instance.jarak_lokasi_meter = self.cleaned_data.get('distance_meters')

        if commit:
            instance.save()

        return instance

    def _read_decimal(self, raw_value):
        raw_value = str(raw_value or '').strip()
        if not raw_value:
            return None

        try:
            return Decimal(raw_value)
        except (InvalidOperation, TypeError, ValueError):
            return None

    def _read_float(self, raw_value):
        raw_value = str(raw_value or '').strip()
        if not raw_value:
            return None

        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return None

    def _has_allowed_content_type(self, uploaded_file, allowed_types):
        content_type = (getattr(uploaded_file, 'content_type', '') or '').lower()
        return any(
            content_type == allowed_type or content_type.startswith(f'{allowed_type};')
            for allowed_type in allowed_types
        )


def calculate_distance_meters(latitude, longitude, target_latitude, target_longitude):
    latitude = float(latitude)
    longitude = float(longitude)
    earth_radius = 6371000
    lat1, lat2 = radians(latitude), radians(target_latitude)
    delta_lat = radians(target_latitude - latitude)
    delta_lon = radians(target_longitude - longitude)
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return earth_radius * 2 * asin(sqrt(value))


class ModulPraktikumForm(forms.ModelForm):
    class Meta:
        model = ModulPraktikum
        fields = ['matkul', 'nomor', 'judul', 'file']
        widgets = {
            'nomor': forms.NumberInput(attrs={'min': 1}),
            'judul': forms.TextInput(attrs={'placeholder': 'Judul atau materi modul'}),
            'file': forms.FileInput(attrs={'accept': '.pdf,.doc,.docx,.ppt,.pptx,.zip'}),
        }


class PesertaPraktikumBulkForm(forms.Form):
    matkul = forms.ModelChoiceField(label='Mata kuliah dan kelas', queryset=None)
    daftar_mahasiswa = forms.CharField(
        label='Daftar mahasiswa',
        widget=forms.Textarea(attrs={
            'rows': 12,
            'placeholder': '064002000001, Nama Mahasiswa\n064002000002, Nama Mahasiswa Kedua',
        }),
        help_text='Satu mahasiswa per baris dengan format NIM, Nama. Bisa memakai koma, titik koma, atau tab.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.pendaftaran_asleb.models import MataKuliahAsleb
        self.fields['matkul'].queryset = MataKuliahAsleb.objects.filter(aktif=True)

    def clean_daftar_mahasiswa(self):
        rows = []
        errors = []
        seen = set()
        for line_number, raw_line in enumerate(self.cleaned_data['daftar_mahasiswa'].splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            normalized = line.replace('\t', ',').replace(';', ',')
            parts = [part.strip() for part in normalized.split(',', 1)]
            if len(parts) != 2 or not parts[0] or not parts[1]:
                errors.append(f'Baris {line_number}: gunakan format NIM, Nama.')
                continue
            nim, nama = parts
            if not nim.isdigit():
                errors.append(f'Baris {line_number}: NIM hanya boleh berisi angka.')
                continue
            if nim in seen:
                continue
            seen.add(nim)
            rows.append({'nim': nim, 'nama': nama})
        if errors:
            raise forms.ValidationError(errors)
        if not rows:
            raise forms.ValidationError('Masukkan minimal satu mahasiswa.')
        return rows


class HasilPraktikumMahasiswaForm(forms.ModelForm):
    class Meta:
        model = HasilPraktikumMahasiswa
        fields = ['status_absensi', 'nilai', 'catatan']
        widgets = {
            'nilai': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': '0.01', 'placeholder': '0-100'}),
            'catatan': forms.TextInput(attrs={'placeholder': 'Opsional'}),
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
