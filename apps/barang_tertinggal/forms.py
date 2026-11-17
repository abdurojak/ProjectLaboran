from django import forms
from PIL import Image, UnidentifiedImageError

from .models import BarangTertinggal


class BarangTertinggalForm(forms.ModelForm):
    class Meta:
        model = BarangTertinggal
        fields = [
            'nama_barang',
            'jenis_barang',
            'jumlah_barang',
            'foto',
            'foto_pengambil',
            'lokasi_ditemukan',
            'tanggal_ditemukan',
            'tanggal_diambil',
            'nama_pemilik',
            'nim_pemilik',
            'nomor_whatsapp',
            'status',
        ]
        widgets = {
            'foto': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
            'foto_pengambil': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/jpeg', 'tabindex': '-1'}),
            'tanggal_ditemukan': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'tanggal_diambil': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'nomor_whatsapp': forms.TextInput(attrs={'inputmode': 'tel', 'autocomplete': 'tel', 'placeholder': '08... atau +62...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('status') == 'diambil' and not (
            cleaned_data.get('foto_pengambil') or self.instance.foto_pengambil
        ):
            self.add_error('foto_pengambil', 'Foto orang yang mengambil barang wajib diambil langsung dari kamera.')
        return cleaned_data

    def clean_foto_pengambil(self):
        photo = self.cleaned_data.get('foto_pengambil')
        if not photo:
            return photo
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Foto pengambil maksimal 5 MB.')
        try:
            photo.seek(0)
            if Image.open(photo).format != 'JPEG':
                raise forms.ValidationError('Foto pengambil harus berformat JPG dari kamera.')
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise forms.ValidationError('Foto pengambil tidak valid.') from exc
        finally:
            photo.seek(0)
        return photo

    def save(self, commit=True):
        instance = super().save(commit=False)
        hapus_foto = self.data.get('hapus_foto') == '1'

        if hapus_foto:
            instance.foto = None

        if commit:
            instance.save()
            self.save_m2m()

        return instance
