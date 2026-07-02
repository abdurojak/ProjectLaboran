from django import forms

from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb, RiwayatAsleb
from apps.ruangan.models import RuanganLab

from .models import JadwalPraktikum


class JadwalPraktikumForm(forms.ModelForm):
    matkul = forms.ModelChoiceField(
        queryset=MataKuliahAsleb.objects.none(),
        empty_label='Pilih mata kuliah',
        label='Matkul',
        widget=forms.Select(attrs={'class': 'min-h-12'}),
    )
    ruangan_tambahan = forms.ModelChoiceField(
        queryset=RuanganLab.objects.none(),
        required=False,
        empty_label='Tidak ada ruangan tambahan',
        label='Ruangan Tambahan',
        widget=forms.Select(attrs={'class': 'min-h-12'}),
        help_text=(
            'Opsional untuk kelas besar. Saat ini gabungan dua lab hanya berlaku untuk '
            'Lab Rekayasa Perangkat Lunak dan Lab Sistem Keamanan Informasi.'
        ),
    )

    def __init__(self, *args, **kwargs):
        self.current_pengguna = kwargs.pop('current_pengguna', None)
        super().__init__(*args, **kwargs)
        self.fields['matkul'].queryset = self.get_matkul_queryset()
        self.fields['matkul'].initial = self.get_initial_matkul()
        room_queryset = self.get_optimal_room_queryset()
        self.fields['ruangan'].queryset = room_queryset
        self.fields['ruangan_tambahan'].queryset = RuanganLab.objects.filter(
            aktif=True,
            kode__in=['LAB-RPL', 'LAB-SKI'],
        )
        self.fields['ruangan_tambahan'].help_text = 'Hanya untuk pasangan Lab RPL dan Lab SKI. Lab lain tidak dapat memakai ruang tambahan.'
        selected_matkul = self.get_selected_matkul()
        self.participant_count = selected_matkul.peserta_praktikum.filter(aktif=True).count() if selected_matkul else 0

    class Meta:
        model = JadwalPraktikum
        fields = [
            'matkul',
            'ruangan',
            'ruangan_tambahan',
            'hari',
            'waktu_mulai',
            'waktu_selesai',
            'catatan',
        ]
        widgets = {
            'waktu_mulai': forms.TimeInput(attrs={'type': 'time', 'step': 1800, 'min': '07:30', 'max': '18:00'}),
            'waktu_selesai': forms.TimeInput(attrs={'type': 'time', 'step': 1800, 'min': '07:30', 'max': '18:00'}),
            'catatan': forms.Textarea(attrs={'rows': 4}),
        }

    def get_matkul_queryset(self):
        queryset = MataKuliahAsleb.objects.filter(aktif=True)
        if self.current_pengguna and self.current_pengguna.role == 'asisten_lab':
            registration_ids = PendaftaranAsleb.objects.filter(
                nim=self.current_pengguna.nim_nik,
                status__in=['diterima', 'digenerate'],
            ).values_list('matkul_id', flat=True)
            history_ids = RiwayatAsleb.objects.filter(
                nim=self.current_pengguna.nim_nik,
            ).values_list('matkul_id', flat=True)
            return queryset.filter(pk__in=set(registration_ids) | set(history_ids)).distinct()
        return queryset

    def get_initial_matkul(self):
        if not self.instance or not self.instance.pk:
            return None

        for matkul in self.fields['matkul'].queryset:
            if str(matkul) == self.instance.mata_kuliah:
                return matkul.pk
        return None

    def get_selected_matkul(self):
        matkul_id = self.data.get('matkul') if self.is_bound else (self.initial.get('matkul') or self.fields['matkul'].initial)
        if not matkul_id:
            matkul_id = self.get_initial_matkul()
        try:
            return self.fields['matkul'].queryset.get(pk=matkul_id) if matkul_id else None
        except (MataKuliahAsleb.DoesNotExist, ValueError, TypeError):
            return None

    def get_optimal_room_queryset(self):
        queryset = RuanganLab.objects.filter(aktif=True).order_by('kapasitas', 'nama')
        matkul = self.get_selected_matkul()
        if not matkul:
            if self.current_pengguna and self.current_pengguna.role == 'asisten_lab':
                return queryset.none()
            return queryset

        participant_count = matkul.peserta_praktikum.filter(aktif=True).count()
        if not participant_count:
            if self.current_pengguna and self.current_pengguna.role == 'asisten_lab':
                return queryset.none()
            return queryset
        return queryset.filter(kapasitas__gte=participant_count)

    def clean(self):
        cleaned_data = super().clean()
        matkul = cleaned_data.get('matkul')
        ruangan = cleaned_data.get('ruangan')
        tambahan = cleaned_data.get('ruangan_tambahan')
        participant_count = matkul.peserta_praktikum.filter(aktif=True).count() if matkul else 0
        if matkul and self.current_pengguna and self.current_pengguna.role == 'asisten_lab' and not participant_count:
            self.add_error('ruangan', 'Laboran harus menginput mahasiswa mata kuliah ini sebelum Asisten Lab memilih laboratorium.')
        if matkul and ruangan:
            if participant_count and (ruangan.kapasitas or 0) < participant_count:
                self.add_error('ruangan', f'Kapasitas lab hanya {ruangan.kapasitas or 0}, sedangkan peserta aktif berjumlah {participant_count}.')
        if tambahan and ruangan:
            selected_codes = frozenset({ruangan.kode, tambahan.kode})
            if selected_codes not in JadwalPraktikum.ALLOWED_COMBINED_ROOM_CODE_SETS:
                self.add_error('ruangan_tambahan', 'Ruang tambahan hanya berlaku untuk pasangan Lab RPL dan Lab SKI.')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        matkul = self.cleaned_data['matkul']
        instance.mata_kuliah = str(matkul)
        instance.kelas = matkul.kelas
        instance.pengampu = matkul.dosen

        if commit:
            instance.save()
            self.save_m2m()

        return instance
