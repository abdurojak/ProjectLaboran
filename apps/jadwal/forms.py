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
        room_queryset = RuanganLab.objects.filter(aktif=True).order_by('nama')
        self.fields['ruangan'].queryset = room_queryset
        self.fields['ruangan_tambahan'].queryset = room_queryset

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
