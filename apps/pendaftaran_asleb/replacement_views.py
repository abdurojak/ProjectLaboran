from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.asleb.models import HonorReassignment
from apps.core.permissions import can_manage_lab_operations

from .models import AslabAssignment, AslabOffer, AslabReplacement, LimitedReplacementOpening, PendaftaranAsleb
from .replacement_forms import (
    DeclineOfferForm, DirectOfferForm, EndAssignmentForm, LimitedOpeningForm,
    ReplacementCandidateForm, VerificationForm,
)
from .replacement_services import (
    accept_offer, activate_replacement, close_limited_registration, create_direct_offer,
    decline_offer, end_assignment_for_replacement, open_limited_registration,
    return_offer_for_revision, select_limited_candidate, submit_offer_registration,
)


def _current(request):
    return getattr(request, 'current_pengguna', None)


def _error_text(exc):
    return ' '.join(exc.messages) if hasattr(exc, 'messages') else str(exc)


class LaboranReplacementMixin:
    def dispatch(self, request, *args, **kwargs):
        if not can_manage_lab_operations(_current(request)):
            messages.error(request, 'Alur penggantian aslab hanya tersedia untuk Laboran.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)


class ReplacementListView(LaboranReplacementMixin, ListView):
    model = AslabReplacement
    template_name = 'pendaftaran_asleb/replacement_list.html'
    context_object_name = 'replacements'

    def get_queryset(self):
        return AslabReplacement.objects.select_related(
            'slot__matkul', 'slot__periode', 'outgoing_assignment__asleb',
            'incoming_assignment__asleb',
        ).prefetch_related(
            'offers__candidate',
            Prefetch('honor_reassignments', queryset=HonorReassignment.objects.select_related('honor')),
        )


class ReplacementDetailView(LaboranReplacementMixin, DetailView):
    model = AslabReplacement
    template_name = 'pendaftaran_asleb/replacement_detail.html'
    context_object_name = 'replacement'

    def get_queryset(self):
        return AslabReplacement.objects.select_related(
            'slot__matkul', 'slot__periode', 'outgoing_assignment__asleb',
            'incoming_assignment__asleb', 'limited_opening',
        ).prefetch_related('offers__candidate', 'offers__registration', 'audit_entries', 'honor_reassignments')


class EndAssignmentView(LaboranReplacementMixin, View):
    template_name = 'pendaftaran_asleb/replacement_end_form.html'

    def assignment(self, assignment_id):
        return get_object_or_404(
            AslabAssignment.objects.select_related('asleb', 'slot__matkul', 'slot__periode'),
            pk=assignment_id,
        )

    def get(self, request, assignment_id):
        assignment = self.assignment(assignment_id)
        form = EndAssignmentForm(initial={'effective_date': assignment.slot.periode.selesai})
        return render(request, self.template_name, {'assignment': assignment, 'form': form})

    def post(self, request, assignment_id):
        assignment = self.assignment(assignment_id)
        form = EndAssignmentForm(request.POST)
        if form.is_valid():
            try:
                replacement = end_assignment_for_replacement(
                    assignment_id=assignment.pk, actor=_current(request), **form.cleaned_data,
                )
            except ValidationError as exc:
                form.add_error(None, _error_text(exc))
            else:
                messages.success(request, 'Masa tugas diakhiri dan proses penggantian dibuat.')
                return redirect('pendaftaran_asleb:replacement_detail', pk=replacement.pk)
        return render(request, self.template_name, {'assignment': assignment, 'form': form})


class CreateOfferView(LaboranReplacementMixin, View):
    template_name = 'pendaftaran_asleb/replacement_offer_form.html'

    def replacement(self, pk):
        return get_object_or_404(AslabReplacement.objects.select_related('slot__matkul', 'slot__periode'), pk=pk)

    def get(self, request, pk):
        replacement = self.replacement(pk)
        return render(request, self.template_name, {'replacement': replacement, 'form': DirectOfferForm(replacement=replacement, actor=_current(request))})

    def post(self, request, pk):
        replacement = self.replacement(pk)
        form = DirectOfferForm(request.POST, replacement=replacement, actor=_current(request))
        if form.is_valid():
            try:
                create_direct_offer(replacement_id=pk, candidate_id=form.cleaned_data['candidate'].pk, deadline=form.cleaned_data['deadline'], actor=_current(request))
            except ValidationError as exc:
                form.add_error(None, _error_text(exc))
            else:
                messages.success(request, 'Tawaran penggantian telah dikirim.')
                return redirect('pendaftaran_asleb:replacement_detail', pk=pk)
        return render(request, self.template_name, {'replacement': replacement, 'form': form})


class CandidateOfferMixin:
    def offer(self, pk):
        user = _current(self.request)
        if not user:
            raise Http404
        return get_object_or_404(
            AslabOffer.objects.select_related('candidate', 'registration', 'replacement__slot__matkul', 'replacement__slot__periode', 'replacement__outgoing_assignment__asleb'),
            pk=pk, candidate=user,
        )


class AcceptOfferView(CandidateOfferMixin, View):
    template_name = 'pendaftaran_asleb/replacement_offer_detail.html'

    def get(self, request, pk):
        return render(request, self.template_name, {'offer': self.offer(pk), 'decline_form': DeclineOfferForm()})

    def post(self, request, pk):
        offer = self.offer(pk)
        try:
            accept_offer(offer_id=offer.pk, candidate=_current(request))
        except ValidationError as exc:
            messages.error(request, _error_text(exc))
            return redirect('pendaftaran_asleb:replacement_offer_accept', pk=pk)
        messages.success(request, 'Tawaran diterima. Lengkapi data sebelum batas waktu.')
        return redirect('pendaftaran_asleb:replacement_candidate_data', pk=pk)


class DeclineOfferView(CandidateOfferMixin, View):
    def get(self, request, pk):
        self.offer(pk)
        return HttpResponseNotAllowed(['POST'])

    def post(self, request, pk):
        offer = self.offer(pk)
        form = DeclineOfferForm(request.POST)
        if form.is_valid():
            try:
                decline_offer(offer_id=offer.pk, candidate=_current(request), reason=form.cleaned_data['reason'])
            except ValidationError as exc:
                messages.error(request, _error_text(exc))
            else:
                messages.success(request, 'Tawaran telah ditolak.')
                return redirect('dashboard:home')
        return redirect('pendaftaran_asleb:replacement_offer_accept', pk=pk)


class CandidateSubmissionView(CandidateOfferMixin, View):
    template_name = 'pendaftaran_asleb/replacement_candidate_form.html'

    def get(self, request, pk):
        offer = self.offer(pk)
        form = ReplacementCandidateForm(offer=offer, candidate=_current(request))
        return render(request, self.template_name, {'offer': offer, 'form': form})

    def post(self, request, pk):
        offer = self.offer(pk)
        form = ReplacementCandidateForm(request.POST, request.FILES, offer=offer, candidate=_current(request))
        if form.is_valid():
            try:
                submit_offer_registration(offer_id=offer.pk, candidate=_current(request), registration_form=form)
            except ValidationError as exc:
                form.add_error(None, _error_text(exc))
            else:
                messages.success(request, 'Data dikirim dan menunggu verifikasi Laboran.')
                return redirect('pendaftaran_asleb:replacement_offer_accept', pk=pk)
        return render(request, self.template_name, {'offer': offer, 'form': form})


class VerifyOfferView(LaboranReplacementMixin, View):
    template_name = 'pendaftaran_asleb/replacement_verify.html'

    def offer(self, pk):
        return get_object_or_404(AslabOffer.objects.select_related('candidate', 'registration', 'replacement__slot__matkul', 'replacement__slot__periode'), pk=pk)

    def get(self, request, pk):
        offer = self.offer(pk)
        return render(request, self.template_name, {'offer': offer, 'form': VerificationForm(initial={'active_date': offer.replacement.effective_date})})

    def post(self, request, pk):
        offer = self.offer(pk)
        form = VerificationForm(request.POST)
        if form.is_valid():
            try:
                if form.cleaned_data['action'] == VerificationForm.ACTION_ACTIVATE:
                    activate_replacement(offer_id=pk, actor=_current(request), active_date=form.cleaned_data['active_date'])
                    message = 'Pengganti berhasil diverifikasi dan diaktifkan.'
                else:
                    return_offer_for_revision(offer_id=pk, actor=_current(request), notes=form.cleaned_data['notes'])
                    message = 'Data dikembalikan kepada kandidat untuk direvisi.'
            except ValidationError as exc:
                form.add_error(None, _error_text(exc))
            else:
                messages.success(request, message)
                return redirect('pendaftaran_asleb:replacement_detail', pk=offer.replacement_id)
        return render(request, self.template_name, {'offer': offer, 'form': form})


class LimitedOpeningView(LaboranReplacementMixin, View):
    template_name = 'pendaftaran_asleb/replacement_opening_form.html'

    def replacement(self, pk):
        return get_object_or_404(AslabReplacement.objects.select_related('slot__matkul', 'slot__periode'), pk=pk)

    def context(self, replacement, form=None):
        opening = LimitedReplacementOpening.objects.filter(replacement=replacement).first()
        applications = PendaftaranAsleb.objects.filter(replacement_process=replacement).select_related('candidate_user')
        return {'replacement': replacement, 'opening': opening, 'applications': applications, 'form': form or LimitedOpeningForm()}

    def get(self, request, pk):
        replacement = self.replacement(pk)
        return render(request, self.template_name, self.context(replacement))

    def post(self, request, pk):
        replacement = self.replacement(pk)
        action = request.POST.get('action', 'open')
        try:
            if action == 'select':
                opening = get_object_or_404(LimitedReplacementOpening, replacement=replacement)
                select_limited_candidate(opening_id=opening.pk, registration_id=request.POST.get('registration_id'), actor=_current(request))
                messages.success(request, 'Kandidat dipilih dan tawaran persetujuan dikirim.')
            elif action == 'close':
                opening = get_object_or_404(LimitedReplacementOpening, replacement=replacement)
                close_limited_registration(opening_id=opening.pk, actor=_current(request))
                messages.success(request, 'Pendaftaran terbatas ditutup.')
            else:
                form = LimitedOpeningForm(request.POST)
                if not form.is_valid():
                    return render(request, self.template_name, self.context(replacement, form))
                data = form.cleaned_data
                open_limited_registration(
                    replacement_id=pk, actor=_current(request), opens_at=data['opens_at'],
                    closes_at=data['closes_at'], program_studi=data['program_studi'],
                    cohort=data['cohort'], allowed_candidate_ids=data['allowed_candidates'].values_list('pk', flat=True),
                    requirements=data['requirements'],
                )
                messages.success(request, 'Pendaftaran terbatas dibuka.')
        except (ValidationError, TypeError, ValueError) as exc:
            messages.error(request, _error_text(exc))
        return redirect('pendaftaran_asleb:replacement_opening', pk=pk)
