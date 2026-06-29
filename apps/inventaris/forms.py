from django import forms
from django.forms import inlineformset_factory

from .models import Barang, InventarisBarang, Lokasi, PaketBarang, PaketBarangItem


class InventarisBarangCreateForm(forms.ModelForm):
    lokasi = forms.ModelChoiceField(queryset=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lokasi'].queryset = Lokasi.objects.all()

    class Meta:
        model = InventarisBarang
        fields = ['nama', 'jumlah', 'lokasi', 'foto', 'keterangan']
        widgets = {
            'foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'keterangan': forms.Textarea(attrs={'rows': 4}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        hapus_foto = self.data.get('hapus_foto') == '1'

        if hapus_foto:
            instance.foto = None

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class InventarisBarangUpdateForm(forms.ModelForm):
    class Meta:
        model = InventarisBarang
        fields = ['nama', 'foto', 'keterangan']
        widgets = {
            'foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'keterangan': forms.Textarea(attrs={'rows': 4}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        hapus_foto = self.data.get('hapus_foto') == '1'

        if hapus_foto:
            instance.foto = None

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class BarangForm(forms.ModelForm):
    class Meta:
        model = Barang
        fields = ['lokasi', 'kondisi', 'keterangan']
        widgets = {
            'keterangan': forms.Textarea(attrs={'rows': 4}),
        }


class PaketBarangForm(forms.ModelForm):
    class Meta:
        model = PaketBarang
        fields = ['nama', 'keterangan', 'aktif']
        widgets = {
            'keterangan': forms.Textarea(attrs={'rows': 4}),
        }


class PaketBarangItemForm(forms.ModelForm):
    class Meta:
        model = PaketBarangItem
        fields = ['inventaris', 'jumlah']

    def clean_jumlah(self):
        jumlah = self.cleaned_data['jumlah']
        if jumlah < 1:
            raise forms.ValidationError('Jumlah item paket minimal 1.')
        return jumlah


PaketBarangItemFormSet = inlineformset_factory(
    PaketBarang,
    PaketBarangItem,
    form=PaketBarangItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
