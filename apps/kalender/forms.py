from django import forms

from .models import KegiatanKalender


class KegiatanKalenderForm(forms.ModelForm):
    target_role = forms.MultipleChoiceField(
        choices=KegiatanKalender.ROLE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Bagikan ke role',
        help_text='Khusus admin/laboran. Kosongkan jika kegiatan hanya untuk catatan internal/pribadi.',
    )

    def __init__(self, *args, current_pengguna=None, **kwargs):
        self.current_pengguna = current_pengguna
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields['target_role'].initial = self.instance.target_role_list

        if not self.can_share_to_roles:
            self.fields.pop('target_role', None)
            self.fields.pop('hari_libur', None)
            self.fields.pop('ruangan', None)
        else:
            self.fields['ruangan'].queryset = self.fields['ruangan'].queryset.filter(aktif=True).order_by('nama')

    @property
    def can_share_to_roles(self):
        return bool(self.current_pengguna and self.current_pengguna.role in {'admin', 'laboran'})

    class Meta:
        model = KegiatanKalender
        fields = [
            'judul',
            'tanggal',
            'waktu_mulai',
            'waktu_selesai',
            'lokasi',
            'ruangan',
            'deskripsi',
            'tampilkan_notifikasi',
            'hari_libur',
            'target_role',
        ]
        widgets = {
            'tanggal': forms.DateInput(attrs={'type': 'date'}),
            'waktu_mulai': forms.TimeInput(attrs={'type': 'time'}),
            'waktu_selesai': forms.TimeInput(attrs={'type': 'time'}),
            'deskripsi': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_target_role(self):
        roles = self.cleaned_data.get('target_role', [])
        if not self.can_share_to_roles:
            return ''
        return ','.join(roles)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('ruangan') and not cleaned.get('waktu_selesai'):
            self.add_error('waktu_selesai', 'Waktu selesai wajib diisi untuk pemakaian lab.')
        return cleaned

