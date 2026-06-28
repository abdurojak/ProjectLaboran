from django import forms
from django.conf import settings
from django.utils import timezone
from math import asin, cos, radians, sin, sqrt

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
    latitude = forms.DecimalField(max_digits=10, decimal_places=7, widget=forms.HiddenInput)
    longitude = forms.DecimalField(max_digits=10, decimal_places=7, widget=forms.HiddenInput)
    gps_accuracy = forms.FloatField(widget=forms.HiddenInput)
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
        self.fields['bukti_foto'].required = True

    def clean_bukti_foto(self):
        photo = self.cleaned_data['bukti_foto']
        if photo.content_type not in {'image/jpeg', 'image/png'}:
            raise forms.ValidationError('Bukti foto harus diambil dari kamera dalam format gambar.')
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Ukuran bukti foto maksimal 5 MB.')
        return photo

    def clean_bukti_video(self):
        video = self.cleaned_data['bukti_video']
        if video.content_type not in {'video/webm', 'video/mp4'}:
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
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')
        accuracy = cleaned_data.get('gps_accuracy')
        if latitude is None or longitude is None or accuracy is None:
            raise forms.ValidationError('Lokasi perangkat wajib diaktifkan untuk melakukan absensi.')
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
        instance.latitude = self.cleaned_data['latitude']
        instance.longitude = self.cleaned_data['longitude']
        instance.jarak_lokasi_meter = self.cleaned_data['distance_meters']

        if commit:
            instance.save()

        return instance


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


def get_asleb_matkul(asleb):
    from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb

    registration = PendaftaranAsleb.objects.filter(
        nim=asleb.nim,
        status__in=['diterima', 'digenerate'],
    ).select_related('matkul').order_by('-pk').first()
    if registration:
        return registration.matkul
    return next((matkul for matkul in MataKuliahAsleb.objects.filter(aktif=True) if str(matkul) == asleb.matkul), None)
