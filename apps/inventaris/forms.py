from django import forms
from django.forms import inlineformset_factory

from .models import (
    Barang,
    FotoInventarisBarang,
    InventarisBarang,
    Lokasi,
    PaketBarang,
    PaketBarangItem,
)


MAX_GALLERY_PHOTOS = 8
MAX_GALLERY_PHOTO_SIZE = 5 * 1024 * 1024


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleImageInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultipleImageField, self).clean(item, initial) for item in files]


class InventarisGalleryFormMixin:
    def clean_foto_galeri(self):
        files = self.cleaned_data.get('foto_galeri', [])
        for uploaded_file in files:
            if uploaded_file.size > MAX_GALLERY_PHOTO_SIZE:
                raise forms.ValidationError(
                    f'Ukuran {uploaded_file.name} melebihi batas 5 MB.'
                )

        existing_count = 0
        deleted_count = 0
        if self.instance and self.instance.pk:
            existing = self.instance.galeri_foto.all()
            existing_count = existing.count()
            delete_ids = self.data.getlist('hapus_foto_galeri')
            deleted_count = existing.filter(pk__in=delete_ids).count()

        if existing_count - deleted_count + len(files) > MAX_GALLERY_PHOTOS:
            raise forms.ValidationError(
                f'Total foto tambahan maksimal {MAX_GALLERY_PHOTOS}. Hapus foto lama atau kurangi file yang dipilih.'
            )
        return files

    def save_gallery(self, instance):
        delete_ids = self.data.getlist('hapus_foto_galeri')
        if delete_ids:
            instance.galeri_foto.filter(pk__in=delete_ids).delete()

        next_order = (
            instance.galeri_foto.order_by('-urutan').values_list('urutan', flat=True).first() or 0
        )
        for offset, uploaded_file in enumerate(self.cleaned_data.get('foto_galeri', []), start=1):
            FotoInventarisBarang.objects.create(
                inventaris=instance,
                foto=uploaded_file,
                urutan=next_order + offset,
            )


class InventarisBarangGalleryForm(InventarisGalleryFormMixin, forms.ModelForm):
    foto_galeri = MultipleImageField(
        required=False,
        label='Foto tambahan',
        help_text='Pilih beberapa foto sekaligus. Maksimal 8 foto per barang dan 5 MB per foto.',
        widget=MultipleImageInput(attrs={
            'class': 'hidden',
            'accept': 'image/jpeg,image/png,image/webp,image/gif',
        }),
    )


class InventarisBarangCreateForm(InventarisBarangGalleryForm):
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


class InventarisBarangUpdateForm(InventarisBarangGalleryForm):
    class Meta:
        model = InventarisBarang
        fields = ['nama', 'jumlah', 'foto', 'keterangan']
        widgets = {
            'jumlah': forms.NumberInput(attrs={'min': 0}),
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
