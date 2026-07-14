import csv
import io

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
    PengumpulanLaporanPraktikum,
    PesertaPraktikum,
    SuratHonorAsleb,
    TugasLaporanPraktikum,
)


ENABLE_CAMERA_LOCATION_CAPTURE = False
MAX_DAILY_MODULE_ATTENDANCE = 2


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
            'nomor_transfer': forms.TextInput(attrs={'placeholder': 'Nomor rekening atau nomor e-wallet'}),
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
            'bukti_foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/jpeg,image/png'}),
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
        self.fields['bukti_video'].required = True
        if not ENABLE_CAMERA_LOCATION_CAPTURE:
            self.fields['bukti_foto'].label = 'Upload Bukti Foto'
            self.fields['bukti_foto'].help_text = 'Upload foto bukti praktikum.'
            self.fields['bukti_video'].label = 'Upload Bukti Video'
            self.fields['bukti_video'].help_text = 'Upload video bukti praktikum.'

    def clean_bukti_foto(self):
        photo = self.cleaned_data['bukti_foto']
        if not self._has_allowed_content_type(photo, ['image/jpeg', 'image/png']):
            raise forms.ValidationError('Bukti foto harus diambil dari kamera dalam format gambar.')
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Ukuran bukti foto maksimal 5 MB.')
        return photo

    def clean_bukti_video(self):
        video = self.cleaned_data['bukti_video']
        if not self._has_allowed_content_type(video, ['video/webm', 'video/mp4']):
            raise forms.ValidationError('Bukti video harus direkam langsung dari kamera.')
        if video.size > 20 * 1024 * 1024:
            raise forms.ValidationError('Ukuran bukti video maksimal 20 MB.')
        return video

    def clean_modul_praktikum(self):
        modul = self.cleaned_data['modul_praktikum']
        if modul.matkul != get_asleb_matkul(self.asleb) or self.jadwal.mata_kuliah != str(modul.matkul):
            raise forms.ValidationError('Modul tidak sesuai dengan mata kuliah pada jadwal aktif.')
        duplicate_qs = AbsensiAsleb.objects.filter(asleb=self.asleb)
        if self.instance and self.instance.pk:
            duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)
        if duplicate_qs.filter(modul_praktikum=modul).exists():
            raise forms.ValidationError('Modul ini sudah pernah diabsen dan tidak dapat dipilih lagi.')
        if duplicate_qs.filter(modul=modul.nomor).exists():
            raise forms.ValidationError(
                f'Modul {modul.nomor} sudah pernah diabsen. Pilih modul lain yang belum dipakai.'
            )
        return modul

    def clean(self):
        cleaned_data = super().clean()
        attendance_date = timezone.localdate()
        latitude = self._read_decimal(cleaned_data.get('latitude'))
        longitude = self._read_decimal(cleaned_data.get('longitude'))
        accuracy = self._read_float(cleaned_data.get('gps_accuracy'))

        daily_attendance = AbsensiAsleb.objects.filter(
            asleb=self.asleb,
            tanggal_praktikum=attendance_date,
        ) if self.asleb else AbsensiAsleb.objects.none()
        if self.instance and self.instance.pk:
            daily_attendance = daily_attendance.exclude(pk=self.instance.pk)
        if daily_attendance.count() >= MAX_DAILY_MODULE_ATTENDANCE:
            raise forms.ValidationError(
                f'Anda sudah melakukan absensi maksimal {MAX_DAILY_MODULE_ATTENDANCE} modul untuk jadwal praktikum hari ini.'
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
            'file': forms.FileInput(attrs={'accept': '.pdf,.doc,.docx'}),
        }

    def clean_file(self):
        uploaded = self.cleaned_data.get('file')
        if not uploaded:
            return uploaded
        lower_name = uploaded.name.lower()
        if not lower_name.endswith(('.pdf', '.doc', '.docx')):
            raise forms.ValidationError('File modul hanya boleh PDF atau Word.')
        if uploaded.size > 15 * 1024 * 1024:
            raise forms.ValidationError('Ukuran file modul maksimal 15 MB.')
        return uploaded


class PesertaPraktikumBulkForm(forms.Form):
    INPUT_MANUAL = 'manual'
    INPUT_CSV = 'csv'
    INPUT_METHOD_CHOICES = [
        (INPUT_MANUAL, 'Tulis manual'),
        (INPUT_CSV, 'Import otomatis dari CSV'),
    ]

    metode_input = forms.ChoiceField(
        label='Metode input',
        choices=INPUT_METHOD_CHOICES,
        widget=forms.RadioSelect,
        initial=INPUT_MANUAL,
    )
    matkul = forms.ModelChoiceField(label='Mata kuliah dan kelas', queryset=None)
    daftar_mahasiswa = forms.CharField(
        label='Daftar mahasiswa',
        widget=forms.Textarea(attrs={
            'rows': 12,
            'placeholder': '064002000001, Nama Mahasiswa\n064002000002, Nama Mahasiswa Kedua',
        }),
        help_text='Satu mahasiswa per baris dengan format NIM, Nama. Bisa memakai koma, titik koma, atau tab.',
        required=False,
    )
    file_csv = forms.FileField(
        label='File CSV peserta',
        required=False,
        help_text='Format yang didukung: CSV dengan kolom Student ID/NIM dan Student Name/Nama.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.pendaftaran_asleb.models import MataKuliahAsleb
        self.fields['matkul'].queryset = MataKuliahAsleb.objects.filter(aktif=True)

    def clean_file_csv(self):
        uploaded = self.cleaned_data.get('file_csv')
        if not uploaded:
            return uploaded
        if not uploaded.name.lower().endswith('.csv'):
            raise forms.ValidationError('File harus berformat CSV.')
        if uploaded.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Ukuran file CSV maksimal 2 MB.')
        return uploaded

    def clean(self):
        cleaned_data = super().clean()
        metode = cleaned_data.get('metode_input') or self.INPUT_MANUAL
        if metode == self.INPUT_CSV:
            uploaded = cleaned_data.get('file_csv')
            if not uploaded:
                self.add_error('file_csv', 'Upload file CSV terlebih dahulu.')
                return cleaned_data
            cleaned_data['peserta_rows'] = self.parse_csv(uploaded)
            return cleaned_data

        raw_text = cleaned_data.get('daftar_mahasiswa', '')
        cleaned_data['peserta_rows'] = self.parse_manual_rows(raw_text)
        return cleaned_data

    def parse_manual_rows(self, raw_text):
        rows = []
        errors = []
        seen = set()
        for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
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

    def parse_csv(self, uploaded):
        try:
            uploaded.seek(0)
            content = uploaded.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            uploaded.seek(0)
            content = uploaded.read().decode('latin-1')

        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            raise forms.ValidationError('CSV tidak memiliki header kolom.')

        normalized_fields = {
            (field or '').strip().lower().replace(' ', '_'): field
            for field in reader.fieldnames
        }
        nim_field = (
            normalized_fields.get('student_id')
            or normalized_fields.get('nim')
            or normalized_fields.get('nim_mahasiswa')
            or normalized_fields.get('id')
        )
        nama_field = (
            normalized_fields.get('student_name')
            or normalized_fields.get('nama')
            or normalized_fields.get('nama_mahasiswa')
            or normalized_fields.get('name')
        )
        if not nim_field or not nama_field:
            raise forms.ValidationError('CSV harus memiliki kolom Student ID/NIM dan Student Name/Nama.')

        rows = []
        errors = []
        seen = set()
        for line_number, row in enumerate(reader, start=2):
            nim = (row.get(nim_field) or '').strip()
            nama = (row.get(nama_field) or '').strip()
            if not nim and not nama:
                continue
            if not nim or not nama:
                errors.append(f'Baris {line_number}: NIM dan Nama wajib terisi.')
                continue
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
            raise forms.ValidationError('CSV tidak berisi data peserta.')
        return rows


class PesertaPraktikumForm(forms.ModelForm):
    class Meta:
        model = PesertaPraktikum
        fields = ['matkul', 'nim', 'nama', 'aktif']
        widgets = {
            'nim': forms.TextInput(attrs={'placeholder': 'NIM mahasiswa'}),
            'nama': forms.TextInput(attrs={'placeholder': 'Nama mahasiswa'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.pendaftaran_asleb.models import MataKuliahAsleb
        self.fields['matkul'].queryset = MataKuliahAsleb.objects.filter(aktif=True).order_by('nama', 'kelas')

    def clean_nim(self):
        nim = self.cleaned_data['nim'].strip()
        if not nim.isdigit():
            raise forms.ValidationError('NIM hanya boleh berisi angka.')
        return nim

    def clean(self):
        cleaned_data = super().clean()
        matkul = cleaned_data.get('matkul')
        nim = cleaned_data.get('nim')
        if matkul and nim:
            duplicate = PesertaPraktikum.objects.filter(matkul=matkul, nim=nim)
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error('nim', 'NIM ini sudah terdaftar pada mata kuliah tersebut.')
        return cleaned_data


class HasilPraktikumMahasiswaForm(forms.ModelForm):
    class Meta:
        model = HasilPraktikumMahasiswa
        fields = ['status_absensi', 'nilai_realtime', 'nilai_laporan', 'catatan']
        widgets = {
            'nilai_realtime': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': '0.01', 'placeholder': '0-100'}),
            'nilai_laporan': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': '0.01', 'placeholder': '0-100'}),
            'catatan': forms.TextInput(attrs={'placeholder': 'Opsional'}),
        }


class TugasLaporanPraktikumForm(forms.ModelForm):
    class Meta:
        model = TugasLaporanPraktikum
        fields = [
            'judul',
            'matkul',
            'modul',
            'pertemuan',
            'deskripsi',
            'format_file',
            'ukuran_maksimal_mb',
            'mulai_pengumpulan',
            'batas_pengumpulan',
            'izinkan_terlambat',
            'asisten_pemeriksa',
            'aktif',
        ]
        widgets = {
            'deskripsi': forms.Textarea(attrs={'rows': 4}),
            'mulai_pengumpulan': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'batas_pengumpulan': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'format_file': forms.TextInput(attrs={'placeholder': 'pdf,doc,docx'}),
        }
        help_texts = {
            'format_file': 'Pisahkan dengan koma. Contoh: pdf,doc,docx',
            'ukuran_maksimal_mb': 'Ukuran maksimal file laporan dalam MB.',
        }

    def __init__(self, *args, **kwargs):
        self.pengguna = kwargs.pop('pengguna', None)
        super().__init__(*args, **kwargs)
        from apps.pendaftaran_asleb.models import MataKuliahAsleb

        matkul_qs = MataKuliahAsleb.objects.filter(aktif=True).order_by('nama', 'kelas')
        if self.pengguna and self.pengguna.role == 'asisten_lab':
            active_labels = list(
                Asleb.objects.filter(nim=self.pengguna.nim_nik, status='aktif')
                .exclude(matkul='')
                .values_list('matkul', flat=True)
            )
            active_ids = [matkul.pk for matkul in matkul_qs if str(matkul) in active_labels]
            matkul_qs = MataKuliahAsleb.objects.filter(pk__in=active_ids).order_by('nama', 'kelas')
        self.fields['matkul'].queryset = matkul_qs
        self.fields['modul'].queryset = ModulPraktikum.objects.select_related('matkul').order_by('matkul__nama', 'matkul__kelas', 'nomor')
        self.fields['asisten_pemeriksa'].queryset = Asleb.objects.filter(status='aktif').order_by('nama')

    def clean(self):
        cleaned_data = super().clean()
        matkul = cleaned_data.get('matkul')
        modul = cleaned_data.get('modul')
        asisten = cleaned_data.get('asisten_pemeriksa')
        mulai = cleaned_data.get('mulai_pengumpulan')
        batas = cleaned_data.get('batas_pengumpulan')
        if modul and matkul and modul.matkul_id != matkul.pk:
            self.add_error('modul', 'Modul harus berasal dari mata kuliah yang dipilih.')
        if asisten and matkul and asisten.matkul != str(matkul):
            self.add_error('asisten_pemeriksa', 'Asisten pemeriksa harus bertugas pada mata kuliah ini.')
        if mulai and batas and batas <= mulai:
            self.add_error('batas_pengumpulan', 'Batas pengumpulan harus setelah waktu mulai.')
        return cleaned_data


class PengumpulanLaporanPraktikumForm(forms.ModelForm):
    class Meta:
        model = PengumpulanLaporanPraktikum
        fields = ['file_laporan']

    def __init__(self, *args, **kwargs):
        self.tugas = kwargs.pop('tugas')
        super().__init__(*args, **kwargs)
        self.fields['file_laporan'].help_text = (
            f'Format: {", ".join(self.tugas.allowed_extensions).upper()}. '
            f'Maksimal {self.tugas.ukuran_maksimal_mb} MB.'
        )

    def clean_file_laporan(self):
        uploaded = self.cleaned_data.get('file_laporan')
        if not uploaded:
            return uploaded
        extension = uploaded.name.lower().rsplit('.', 1)[-1] if '.' in uploaded.name else ''
        if extension not in self.tugas.allowed_extensions:
            raise forms.ValidationError('File laporan hanya boleh sesuai format yang ditentukan tugas.')
        max_size = self.tugas.ukuran_maksimal_mb * 1024 * 1024
        if uploaded.size > max_size:
            raise forms.ValidationError(f'Ukuran file maksimal {self.tugas.ukuran_maksimal_mb} MB.')
        return uploaded


class ReviewLaporanPraktikumForm(forms.ModelForm):
    class Meta:
        model = PengumpulanLaporanPraktikum
        fields = ['status', 'catatan_asisten', 'nilai']
        widgets = {
            'catatan_asisten': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Catatan, komentar, atau instruksi revisi'}),
            'nilai': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': '0.01'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        nilai = cleaned_data.get('nilai')
        if status == PengumpulanLaporanPraktikum.STATUS_DINILAI and nilai is None:
            self.add_error('nilai', 'Nilai wajib diisi jika status sudah dinilai.')
        return cleaned_data


def get_asleb_matkul(asleb):
    from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb

    if not asleb or asleb.status != 'aktif':
        return None

    active_match = next(
        (
            matkul for matkul in MataKuliahAsleb.objects.filter(aktif=True)
            if str(matkul) == asleb.matkul
        ),
        None,
    )
    if active_match:
        return active_match

    registration = PendaftaranAsleb.objects.filter(
        nim=asleb.nim,
        status='digenerate',
    ).select_related('matkul').order_by('-pk').first()
    if registration:
        return registration.matkul
    return None
