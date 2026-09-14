from datetime import timedelta

from django import forms

from apps.inventaris.models import Barang, PaketBarang
from .models import PengajuanPerpanjangan, PeminjamanAlat
from .services import adjust_return_date, get_credit_profile


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
            'tanggal_pinjam': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'tanggal_kembali': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'catatan': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        self.current_pengguna = kwargs.pop('current_pengguna', None)
        self.current_group_barang_ids = set(kwargs.pop('current_group_barang_ids', []))
        super().__init__(*args, **kwargs)
        self.fields['barang'].queryset = Barang.objects.select_related('inventaris', 'lokasi')
        self.fields['paket'].queryset = PaketBarang.objects.filter(aktif=True).prefetch_related('items__inventaris')
        self.fields['barang'].label = 'Detail Barang'
        self.fields['barang'].required = False
        if self.instance.pk and self.instance.barang_id:
            self.fields['barang'].required = False
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
        tanggal_pinjam = cleaned_data.get('tanggal_pinjam')
        tanggal_kembali = cleaned_data.get('tanggal_kembali')
        if paket:
            cleaned_data['selected_barang_ids'] = ''

        if not self.instance.pk and not selected_barang_ids and not paket:
            self.add_error('barang', 'Pilih minimal satu detail barang.')
            return cleaned_data

        nim = cleaned_data.get('nim', '')
        if tanggal_pinjam and tanggal_kembali and tanggal_kembali >= tanggal_pinjam:
            credit_profile = get_credit_profile(nim) if nim else None
            if credit_profile and not credit_profile.can_submit and not self.instance.pk:
                self.add_error(
                    'tanggal_kembali',
                    'Masih ada peminjaman terlambat. Kembalikan barang tersebut sebelum mengajukan lagi.',
                )
            max_days = credit_profile.max_loan_days if credit_profile else 7
            requested_days = (tanggal_kembali - tanggal_pinjam).days
            if requested_days > max_days:
                self.add_error(
                    'tanggal_kembali',
                    f'Masa peminjaman maksimal {max_days} hari berdasarkan skor kredit peminjam.',
                )
            else:
                adjusted_date = adjust_return_date(tanggal_kembali)
                if adjusted_date != tanggal_kembali:
                    self.return_date_adjusted_from = tanggal_kembali
                    cleaned_data['tanggal_kembali'] = adjusted_date

        if self.instance.pk and not barang and not selected_barang_ids:
            self.add_error('barang', 'Pilih detail barang.')
            return cleaned_data

        if not barang:
            return cleaned_data

        sedang_dipinjam = barang.sedang_dipinjam
        if self.instance.pk and barang.pk in self.current_group_barang_ids:
            sedang_dipinjam = barang.peminjaman.exclude(pk=self.instance.pk).filter(
                status__in=['dipinjam', 'hilang', 'rusak'],
            ).exclude(barang_id__in=self.current_group_barang_ids).exists()

        if status in ['diajukan', 'dipinjam'] and sedang_dipinjam:
            self.add_error('barang', 'Detail barang ini sedang dipinjam.')

        return cleaned_data


class PengajuanPerpanjanganForm(forms.ModelForm):
    class Meta:
        model = PengajuanPerpanjangan
        fields = [
            'tanggal_kembali_diminta',
            'alasan',
            'kondisi_barang',
            'keterangan_kondisi',
            'pernyataan_jujur',
        ]
        widgets = {
            'tanggal_kembali_diminta': forms.DateInput(attrs={'type': 'date'}),
            'alasan': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Jelaskan alasan perpanjangan.'}),
            'kondisi_barang': forms.RadioSelect(attrs={
                'class': 'h-4 w-4 shrink-0 accent-cyan-700',
            }),
            'keterangan_kondisi': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Jelaskan kerusakan, kendala, atau perubahan kondisi barang.',
            }),
            'pernyataan_jujur': forms.CheckboxInput(attrs={
                'class': 'mt-1 h-5 w-5 shrink-0 rounded accent-cyan-700',
            }),
        }
        labels = {
            'tanggal_kembali_diminta': 'Tanggal kembali baru',
            'alasan': 'Alasan perpanjangan',
            'kondisi_barang': 'Apakah kondisi barang masih baik?',
            'keterangan_kondisi': 'Keterangan kondisi barang',
            'pernyataan_jujur': (
                'Saya menyatakan seluruh informasi yang saya tulis benar dan dapat dipertanggungjawabkan.'
            ),
        }
        error_messages = {
            'pernyataan_jujur': {
                'required': 'Pernyataan kejujuran wajib disetujui sebelum mengajukan perpanjangan.',
            },
        }

    def __init__(self, *args, transaksi, credit_profile, **kwargs):
        self.transaksi = transaksi
        self.credit_profile = credit_profile
        super().__init__(*args, **kwargs)
        self.fields['tanggal_kembali_diminta'].widget.attrs.update({
            'min': (transaksi.tanggal_kembali + timedelta(days=1)).isoformat(),
            'max': (transaksi.tanggal_kembali + timedelta(days=credit_profile.max_loan_days)).isoformat(),
        })
        self.fields['pernyataan_jujur'].required = True

    def clean_alasan(self):
        alasan = self.cleaned_data['alasan'].strip()
        if len(alasan) < 10:
            raise forms.ValidationError('Alasan perpanjangan minimal 10 karakter.')
        return alasan

    def clean_tanggal_kembali_diminta(self):
        requested_date = self.cleaned_data['tanggal_kembali_diminta']
        current_date = self.transaksi.tanggal_kembali
        if requested_date <= current_date:
            raise forms.ValidationError('Tanggal baru harus setelah tanggal kembali saat ini.')

        extension_days = (requested_date - current_date).days
        max_days = self.credit_profile.max_loan_days
        if extension_days > max_days:
            raise forms.ValidationError(
                f'Perpanjangan maksimal {max_days} hari berdasarkan skor kredit peminjam.'
            )
        return adjust_return_date(requested_date)

    def clean(self):
        cleaned_data = super().clean()
        kondisi = cleaned_data.get('kondisi_barang')
        keterangan = (cleaned_data.get('keterangan_kondisi') or '').strip()
        if kondisi == 'tidak_baik' and len(keterangan) < 10:
            self.add_error(
                'keterangan_kondisi',
                'Jelaskan masalah atau kerusakan barang minimal 10 karakter.',
            )
        cleaned_data['keterangan_kondisi'] = keterangan
        return cleaned_data
