from datetime import timedelta

from django import forms
from django.utils import timezone

from apps.pengguna.models import Pengguna

from .forms import PendaftaranAslebForm
from .models import AslabOffer, PendaftaranAsleb
from .replacement_services import eligible_candidate_queryset


class DirectOfferForm(forms.Form):
    candidate = forms.ModelChoiceField(queryset=Pengguna.objects.none())
    deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )

    def __init__(self, *args, replacement=None, actor=None, **kwargs):
        self.replacement = replacement
        self.actor = actor
        super().__init__(*args, **kwargs)
        self.fields['deadline'].initial = timezone.now() + timedelta(days=3)
        if replacement is not None:
            self.fields['candidate'].queryset = eligible_candidate_queryset(replacement)

    def clean_deadline(self):
        deadline = self.cleaned_data['deadline']
        if timezone.is_naive(deadline) or deadline <= timezone.now():
            raise forms.ValidationError('Batas persetujuan harus berupa waktu masa depan.')
        return deadline


class EndAssignmentForm(forms.Form):
    reason_type = forms.ChoiceField(choices=[
        ('resignation', 'Mengundurkan diri'),
        ('dismissal', 'Diberhentikan'),
        ('other', 'Alasan lain'),
    ])
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}))
    effective_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    method = forms.ChoiceField(choices=[
        ('undecided', 'Tentukan nanti'),
        ('direct_offer', 'Penawaran langsung'),
        ('limited_registration', 'Pendaftaran terbatas'),
    ])


class DeclineOfferForm(forms.Form):
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))


class LimitedOpeningForm(forms.Form):
    opens_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    closes_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    program_studi = forms.CharField(required=False)
    cohort = forms.IntegerField(required=False, min_value=1, label='Angkatan')
    allowed_candidates = forms.ModelMultipleChoiceField(
        queryset=Pengguna.objects.none(), required=False, label='Kandidat yang diizinkan',
    )
    requirements = forms.CharField(
        required=False, label='Persyaratan tambahan', widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['allowed_candidates'].queryset = Pengguna.objects.filter(
            role='mahasiswa', is_verified=True,
        ).order_by('nama_pengguna')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('opens_at') and cleaned.get('closes_at'):
            if cleaned['closes_at'] <= cleaned['opens_at']:
                self.add_error('closes_at', 'Waktu penutupan harus setelah pembukaan.')
        return cleaned


class VerificationForm(forms.Form):
    ACTION_ACTIVATE = 'activate'
    ACTION_REVISION = 'revision'
    action = forms.ChoiceField(choices=[
        (ACTION_ACTIVATE, 'Verifikasi dan aktifkan'),
        (ACTION_REVISION, 'Kembalikan untuk revisi'),
    ])
    active_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('action') == self.ACTION_ACTIVATE and not cleaned.get('active_date'):
            self.add_error('active_date', 'Tanggal aktif wajib diisi.')
        if cleaned.get('action') == self.ACTION_REVISION and not (cleaned.get('notes') or '').strip():
            self.add_error('notes', 'Catatan revisi wajib diisi.')
        return cleaned


class ReplacementCandidateForm(PendaftaranAslebForm):
    """Candidate form bound to one offer; the service performs the authoritative save."""

    def __init__(self, *args, offer, candidate, **kwargs):
        self.offer = offer
        self.candidate = candidate
        if offer.registration_id and 'instance' not in kwargs:
            kwargs['instance'] = offer.registration
        super().__init__(*args, **kwargs)
        slot = offer.replacement.slot
        self.fields['matkul'].queryset = self.fields['matkul'].queryset.filter(pk=slot.matkul_id)
        self.fields['matkul'].initial = slot.matkul_id
        self.fields['rekening'].required = True
        self.fields['nama_pemilik_rekening'].required = True
        for name in ('nama', 'nim', 'no_hp', 'email', 'program_studi'):
            self.fields[name].required = False
            self.fields[name].widget = forms.HiddenInput()
        identity = {
            'nama': candidate.nama_pengguna, 'nim': candidate.nim_nik,
            'no_hp': candidate.no_hp, 'email': candidate.email,
            'program_studi': candidate.prodi,
        }
        for name, value in identity.items():
            self.fields[name].initial = value
        if self.instance.pk:
            self.fields['transkrip'].required = False
            self.fields['tanda_tangan'].required = False

    class Meta(PendaftaranAslebForm.Meta):
        fields = [
            'nama', 'nim', 'no_hp', 'email', 'program_studi', 'semester', 'matkul',
            'transkrip', 'tanda_tangan', 'metode_rekening', 'rekening',
            'nama_pemilik_rekening', 'nilai_transkrip', 'alasan',
        ]

    def clean(self):
        cleaned = super().clean()
        slot = self.offer.replacement.slot
        submitted_course = cleaned.get('matkul')
        if submitted_course and submitted_course.pk != slot.matkul_id:
            self.add_error('matkul', 'Mata kuliah tidak dapat diubah.')
        cleaned['matkul'] = slot.matkul
        cleaned.update({
            'nama': self.candidate.nama_pengguna, 'nim': self.candidate.nim_nik,
            'no_hp': self.candidate.no_hp, 'email': self.candidate.email,
            'program_studi': self.candidate.prodi,
        })
        if not cleaned.get('transkrip') and not getattr(self.instance, 'transkrip', None):
            self.add_error('transkrip', 'Transkrip wajib diunggah.')
        if not cleaned.get('tanda_tangan') and not getattr(self.instance, 'tanda_tangan', None):
            self.add_error('tanda_tangan', 'Tanda tangan wajib diunggah.')
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.nama = self.candidate.nama_pengguna
        instance.nim = self.candidate.nim_nik
        instance.no_hp = self.candidate.no_hp
        instance.email = self.candidate.email
        instance.program_studi = self.candidate.prodi
        instance.matkul = self.offer.replacement.slot.matkul
        instance.periode = self.offer.replacement.slot.periode
        instance.jenis = PendaftaranAsleb.JENIS_REPLACEMENT
        instance.replacement_process = self.offer.replacement
        instance.candidate_user = self.candidate
        instance.status = 'diajukan'
        if commit:
            instance.save()
        return instance


class LimitedReplacementApplicationForm(PendaftaranAslebForm):
    """Application data bound to a locked limited opening and candidate."""

    def __init__(self, *args, opening, candidate, **kwargs):
        self.opening = opening
        self.candidate = candidate
        super().__init__(*args, **kwargs)
        slot = opening.replacement.slot
        self.fields['matkul'].queryset = self.fields['matkul'].queryset.filter(pk=slot.matkul_id)
        self.fields['matkul'].initial = slot.matkul_id
        self.fields['rekening'].required = True
        self.fields['nama_pemilik_rekening'].required = True
        for name in ('nama', 'nim', 'no_hp', 'email', 'program_studi'):
            self.fields[name].required = False
            self.fields[name].widget = forms.HiddenInput()

    class Meta(PendaftaranAslebForm.Meta):
        fields = [
            'nama', 'nim', 'no_hp', 'email', 'program_studi', 'semester', 'matkul',
            'transkrip', 'tanda_tangan', 'metode_rekening', 'rekening',
            'nama_pemilik_rekening', 'nilai_transkrip', 'alasan',
        ]

    def clean(self):
        cleaned = super().clean()
        slot = self.opening.replacement.slot
        submitted_course = cleaned.get('matkul')
        if submitted_course and submitted_course.pk != slot.matkul_id:
            self.add_error('matkul', 'Mata kuliah tidak dapat diubah.')
        cleaned.update({
            'nama': self.candidate.nama_pengguna,
            'nim': self.candidate.nim_nik,
            'no_hp': self.candidate.no_hp,
            'email': self.candidate.email,
            'program_studi': self.candidate.prodi,
            'matkul': slot.matkul,
        })
        if not cleaned.get('transkrip'):
            self.add_error('transkrip', 'Transkrip wajib diunggah.')
        if not cleaned.get('tanda_tangan'):
            self.add_error('tanda_tangan', 'Tanda tangan wajib diunggah.')
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        slot = self.opening.replacement.slot
        instance.nama = self.candidate.nama_pengguna
        instance.nim = self.candidate.nim_nik
        instance.no_hp = self.candidate.no_hp
        instance.email = self.candidate.email
        instance.program_studi = self.candidate.prodi
        instance.matkul = slot.matkul
        instance.periode = slot.periode
        instance.jenis = PendaftaranAsleb.JENIS_REPLACEMENT
        instance.replacement_process = self.opening.replacement
        instance.candidate_user = self.candidate
        instance.status = 'diajukan'
        if commit:
            instance.save()
        return instance
