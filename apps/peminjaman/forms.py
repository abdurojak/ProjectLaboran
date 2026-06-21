from django import forms

from apps.inventaris.models import Barang
from .models import PeminjamanAlat


class PeminjamanAlatForm(forms.ModelForm):
    selected_barang_ids = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = PeminjamanAlat
        fields = [
            'barang',
            'nama_peminjam',
            'nim',
            'no_hp',
            'jumlah',
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
        super().__init__(*args, **kwargs)
        self.fields['barang'].queryset = Barang.objects.select_related('inventaris', 'lokasi')
        self.fields['barang'].label = 'Detail Barang'
        self.fields['barang'].required = False
        if self.instance.pk and self.instance.barang_id:
            self.fields['barang'].required = True

    def clean(self):
        cleaned_data = super().clean()
        barang = cleaned_data.get('barang')
        selected_barang_ids = cleaned_data.get('selected_barang_ids')
        jumlah = cleaned_data.get('jumlah')
        status = cleaned_data.get('status')

        if not self.instance.pk and not selected_barang_ids:
            self.add_error('barang', 'Pilih minimal satu detail barang.')
            return cleaned_data

        if self.instance.pk and not barang:
            self.add_error('barang', 'Pilih detail barang.')
            return cleaned_data

        if not barang or not jumlah:
            return cleaned_data

        stok_tersedia = barang.stok_tersedia
        if self.instance.pk and self.instance.barang_id == barang.pk and self.instance.status in ['dipinjam', 'hilang', 'rusak']:
            stok_tersedia += self.instance.jumlah

        if status in ['diajukan', 'dipinjam'] and jumlah > stok_tersedia:
            self.add_error('jumlah', f'Stok tersedia hanya {stok_tersedia} unit.')

        return cleaned_data
