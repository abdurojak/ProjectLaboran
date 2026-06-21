from django import forms

from .models import Barang, InventarisBarang, Lokasi


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
