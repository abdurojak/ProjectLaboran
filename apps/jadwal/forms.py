from django import forms

from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb, RiwayatAsleb
from apps.ruangan.models import GrupRuanganGabungan, RuanganLab

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
            'Opsional untuk kelas besar. Hanya lab dalam grup ruangan gabungan aktif yang dapat dipilih bersama.'
        ),
    )

    def __init__(self, *args, **kwargs):
        self.current_pengguna = kwargs.pop('current_pengguna', None)
        super().__init__(*args, **kwargs)
        self.fields['matkul'].queryset = self.get_matkul_queryset()
        self.fields['matkul'].initial = self.get_initial_matkul()
        room_queryset = self.get_optimal_room_queryset()
        self.fields['ruangan'].queryset = room_queryset
        self.fields['ruangan_tambahan'].queryset = self.get_additional_room_queryset()
        self.fields['ruangan_tambahan'].help_text = 'Hanya lab dalam grup ruangan gabungan aktif yang dapat dipakai sebagai ruangan tambahan.'
        self.combinable_room_options = self.get_combinable_room_options()
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
        eligible_ids = []
        groups = GrupRuanganGabungan.objects.filter(aktif=True).prefetch_related('ruangan')
        for room in queryset:
            if (room.kapasitas or 0) >= participant_count:
                eligible_ids.append(room.pk)
                continue
            for group in groups:
                grouped_rooms = [grouped_room for grouped_room in group.ruangan.all() if grouped_room.aktif]
                if room in grouped_rooms and sum((grouped_room.kapasitas or 0) for grouped_room in grouped_rooms) >= participant_count:
                    eligible_ids.append(room.pk)
                    break
        return queryset.filter(pk__in=eligible_ids)

    def get_additional_room_queryset(self):
        return (
            RuanganLab.objects.filter(aktif=True, grup_gabungan__aktif=True)
            .distinct()
            .order_by('nama')
        )

    def get_combinable_room_options(self):
        groups = GrupRuanganGabungan.objects.filter(aktif=True).prefetch_related('ruangan')
        options = {}
        for group in groups:
            grouped_rooms = [room for room in group.ruangan.all() if room.aktif]
            for room in grouped_rooms:
                options[str(room.pk)] = [
                    {'id': other_room.pk, 'label': str(other_room)}
                    for other_room in grouped_rooms
                    if other_room.pk != room.pk
                ]
        return options

    def clean(self):
        cleaned_data = super().clean()
        matkul = cleaned_data.get('matkul')
        ruangan = cleaned_data.get('ruangan')
        tambahan = cleaned_data.get('ruangan_tambahan')
        participant_count = matkul.peserta_praktikum.filter(aktif=True).count() if matkul else 0
        if matkul and self.current_pengguna and self.current_pengguna.role == 'asisten_lab' and not participant_count:
            self.add_error('ruangan', 'Laboran harus menginput mahasiswa mata kuliah ini sebelum Asisten Lab memilih laboratorium.')
        if tambahan and ruangan:
            if not GrupRuanganGabungan.get_active_pair(ruangan, tambahan):
                self.add_error('ruangan_tambahan', 'Ruangan tambahan hanya berlaku untuk lab dalam grup ruangan gabungan aktif.')
        if matkul and ruangan and participant_count:
            total_capacity = (ruangan.kapasitas or 0)
            if tambahan and GrupRuanganGabungan.get_active_pair(ruangan, tambahan):
                total_capacity += tambahan.kapasitas or 0
            if total_capacity < participant_count:
                self.add_error(
                    'ruangan',
                    f'Kapasitas lab hanya {total_capacity}, sedangkan peserta aktif berjumlah {participant_count}.',
                )
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
