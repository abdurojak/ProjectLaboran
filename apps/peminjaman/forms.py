from django import forms

from apps.inventaris.models import Barang, PaketBarang
from .models import PeminjamanAlat


BORROWER_ROLES = {'mahasiswa', 'asisten_lab'}


class PeminjamanAlatForm(forms.ModelForm):
    selected_barang_ids = forms.CharField(required=False, widget=forms.HiddenInput())
    paket = forms.ModelChoiceField(
        queryset=PaketBarang.objects.none(),
        required=False,
        empty_label='Tidak memakai paket',
    )

    class Meta:
        model = PeminjamanAlat
        fields = [
            'barang',
            'nama_peminjam',
            'nim',
            'no_hp',
            'tanggal_pinjam',
            'tanggal_kembali',
            'status',
            'catatan',
        ]
        widgets = {
            'barang': forms.HiddenInput(),
            'tanggal_pinjam': forms.DateInput(attrs={'type': 'date'}),
            'tanggal_kembali': forms.DateInput(attrs={'type': 'date'}),
            'catatan': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        self.current_pengguna = kwargs.pop('current_pengguna', None)
        super().__init__(*args, **kwargs)
        self.fields['barang'].queryset = Barang.objects.select_related('inventaris', 'lokasi')
        self.fields['paket'].queryset = PaketBarang.objects.filter(aktif=True).prefetch_related('items__inventaris')
        self.fields['barang'].label = 'Detail Barang'
        self.fields['barang'].required = False
        if self.instance.pk and self.instance.barang_id:
            self.fields['barang'].required = True
        if self.current_pengguna and self.current_pengguna.role in BORROWER_ROLES:
            self.fields['nama_peminjam'].initial = self.current_pengguna.nama_pengguna
            self.fields['nim'].initial = self.current_pengguna.nim_nik
            self.fields['no_hp'].initial = self.current_pengguna.no_hp
            self.fields['nama_peminjam'].required = False
            self.fields['nim'].required = False
            self.fields['no_hp'].required = False
            self.fields['nama_peminjam'].widget = forms.HiddenInput()
            self.fields['nim'].widget = forms.HiddenInput()
            self.fields['no_hp'].widget = forms.HiddenInput()
            self.fields['status'].initial = 'diajukan'
            self.fields['status'].required = False
            self.fields['status'].widget = forms.HiddenInput()
        elif self.instance.pk:
            self.fields['status'].disabled = True
            self.fields['status'].help_text = 'Ubah status melalui aksi peminjaman pada dashboard agar alur dan notifikasi tercatat.'

    def clean(self):
        cleaned_data = super().clean()
        if self.current_pengguna and self.current_pengguna.role in BORROWER_ROLES:
            cleaned_data['nama_peminjam'] = self.current_pengguna.nama_pengguna
            cleaned_data['nim'] = self.current_pengguna.nim_nik
            cleaned_data['no_hp'] = self.current_pengguna.no_hp
            cleaned_data['status'] = 'diajukan'

        barang = cleaned_data.get('barang')
        selected_barang_ids = cleaned_data.get('selected_barang_ids')
        paket = cleaned_data.get('paket')
        status = cleaned_data.get('status')
        if paket:
            cleaned_data['selected_barang_ids'] = ''

        if not self.instance.pk and not selected_barang_ids and not paket:
            self.add_error('barang', 'Pilih minimal satu detail barang.')
            return cleaned_data

        if self.instance.pk and not barang:
            self.add_error('barang', 'Pilih detail barang.')
            return cleaned_data

        if not barang:
            return cleaned_data

        sedang_dipinjam = barang.sedang_dipinjam
        if self.instance.pk and self.instance.barang_id == barang.pk:
            sedang_dipinjam = barang.peminjaman.exclude(pk=self.instance.pk).filter(
                status__in=['dipinjam', 'hilang', 'rusak'],
            ).exists()

        if status in ['diajukan', 'dipinjam'] and sedang_dipinjam:
            self.add_error('barang', 'Detail barang ini sedang dipinjam.')

        return cleaned_data
