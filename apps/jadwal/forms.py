from django import forms

from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb
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
            kode=JadwalPraktikum.ADDITIONAL_ROOM_CODE,
        )
        self.fields['ruangan_tambahan'].help_text = 'Opsional. Ruangan tambahan hanya Lab Rekayasa Perangkat Lunak.'
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
            return queryset.filter(
                pendaftaran__nim=self.current_pengguna.nim_nik,
                pendaftaran__status__in=['diterima', 'digenerate'],
            ).distinct()
        return queryset

    def get_initial_matkul(self):
        if not self.instance or not self.instance.pk:
            return None

        for matkul in self.fields['matkul'].queryset:
            if str(matkul) == self.instance.mata_kuliah:
                return matkul.pk
        return None

    def get_selected_matkul(self):
        matkul_id = self.data.get('matkul') if self.is_bound else self.initial.get('matkul')
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
            return queryset

        participant_count = matkul.peserta_praktikum.filter(aktif=True).count()
        if not participant_count:
            return queryset

        capacities = list(
            queryset.filter(kapasitas__gte=participant_count)
            .values_list('kapasitas', flat=True)
            .distinct()
        )
        if not capacities:
            return queryset.none()
        return queryset.filter(kapasitas=min(capacities))

    def clean(self):
        cleaned_data = super().clean()
        matkul = cleaned_data.get('matkul')
        ruangan = cleaned_data.get('ruangan')
        tambahan = cleaned_data.get('ruangan_tambahan')
        if matkul and ruangan:
            participant_count = matkul.peserta_praktikum.filter(aktif=True).count()
            total_capacity = (ruangan.kapasitas or 0) + ((tambahan.kapasitas or 0) if tambahan else 0)
            if participant_count and total_capacity < participant_count:
                self.add_error('ruangan', f'Kapasitas ruangan hanya {total_capacity}, sedangkan peserta aktif berjumlah {participant_count}.')
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
