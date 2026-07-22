from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.asleb.models import Asleb
from apps.core.permissions import can_manage_lab_operations
from apps.pengguna.models import Pengguna

from .models import (
    AslabAssignment, AslabOffer, AslabReplacement, AslabReplacementAudit, AslabSlot,
    PendaftaranAsleb,
)


REASON_STATUS_MAP = {
    'resignation': AslabAssignment.STATUS_RESIGNED,
    'dismissal': AslabAssignment.STATUS_TERMINATED,
    'other': AslabAssignment.STATUS_TERMINATED,
}


def eligible_candidate_queryset(replacement):
    slot = replacement.slot
    assigned_nims = AslabAssignment.objects.filter(
        status=AslabAssignment.STATUS_ACTIVE,
        slot__periode_id=slot.periode_id,
        slot__matkul_id=slot.matkul_id,
    ).values_list('asleb__nim', flat=True)
    conflicting_offers = AslabOffer.objects.filter(
        status__in=AslabOffer.LIVE_STATUSES,
    ).values_list('candidate_id', flat=True)
    live_registrations = PendaftaranAsleb.objects.filter(
        jenis=PendaftaranAsleb.JENIS_REPLACEMENT,
        status__in=PendaftaranAsleb.LIVE_REPLACEMENT_STATUSES,
    ).values_list('candidate_user_id', flat=True)
    return Pengguna.objects.filter(role='mahasiswa', is_verified=True).exclude(
        nim_nik__in=assigned_nims,
    ).exclude(pk__in=conflicting_offers).exclude(pk__in=live_registrations)


def _audit(replacement, actor, action, previous, new, reason='', metadata=None):
    AslabReplacementAudit.objects.create(
        replacement=replacement, actor=actor, action=action, previous_state=previous,
        new_state=new, reason=reason, metadata=metadata or {},
    )


def _lock_offer(offer_id):
    replacement_id = AslabOffer.objects.filter(pk=offer_id).values_list(
        'replacement_id', flat=True).first()
    if replacement_id is None:
        raise ValidationError('Penawaran tidak ditemukan.')
    replacement = AslabReplacement.objects.select_for_update().select_related(
        'slot__periode', 'slot__matkul').get(pk=replacement_id)
    AslabSlot.objects.select_for_update().get(pk=replacement.slot_id)
    offers = list(AslabOffer.objects.select_for_update().filter(
        replacement_id=replacement_id).order_by('pk'))
    offer = next(item for item in offers if item.pk == offer_id)
    return replacement, offer


def _require_owner(offer, candidate):
    if candidate is None or offer.candidate_id != candidate.pk:
        raise ValidationError('Penawaran ini hanya dapat diproses oleh kandidat yang dituju.')


@transaction.atomic
def create_direct_offer(*, replacement_id, candidate_id, deadline, actor):
    if not can_manage_lab_operations(actor):
        raise ValidationError('Hanya laboran yang dapat membuat penawaran.')
    if timezone.is_naive(deadline) or deadline <= timezone.now():
        raise ValidationError('Batas persetujuan harus berupa waktu masa depan.')
    try:
        replacement = AslabReplacement.objects.select_for_update().select_related(
            'slot__periode', 'slot__matkul').get(pk=replacement_id)
    except AslabReplacement.DoesNotExist as exc:
        raise ValidationError('Proses penggantian tidak ditemukan.') from exc
    slot = AslabSlot.objects.select_for_update().get(pk=replacement.slot_id)
    list(AslabOffer.objects.select_for_update().filter(replacement=replacement).order_by('pk'))
    try:
        candidate = Pengguna.objects.select_for_update().get(pk=candidate_id)
    except Pengguna.DoesNotExist as exc:
        raise ValidationError('Kandidat tidak ditemukan.') from exc
    if replacement.status in {AslabReplacement.STATUS_ACTIVE, AslabReplacement.STATUS_CANCELLED}:
        raise ValidationError('Proses penggantian sudah tidak aktif.')
    if slot.status != AslabSlot.STATUS_VACANT:
        raise ValidationError('Slot penggantian tidak lagi kosong.')
    if candidate.role != 'mahasiswa' or not candidate.is_verified:
        raise ValidationError('Kandidat harus mahasiswa terverifikasi.')
    if not eligible_candidate_queryset(replacement).filter(pk=candidate.pk).exists():
        raise ValidationError('Kandidat memiliki penugasan, penawaran, atau pendaftaran aktif yang berkonflik.')
    previous = replacement.status
    try:
        offer = AslabOffer.objects.create(
            replacement=replacement, candidate=candidate, deadline=deadline,
        )
    except IntegrityError as exc:
        raise ValidationError('Proses penggantian sudah memiliki penawaran aktif.') from exc
    replacement.method = AslabReplacement.METHOD_DIRECT_OFFER
    replacement.status = AslabReplacement.STATUS_WAITING_CONSENT
    replacement.save(update_fields=['method', 'status', 'updated_at'])
    _audit(replacement, actor, 'direct_offer_created', previous, replacement.status,
           metadata={'offer_id': offer.pk, 'candidate_id': candidate.pk,
                     'deadline': deadline.isoformat()})
    return offer


@transaction.atomic
def accept_offer(*, offer_id, candidate):
    replacement, offer = _lock_offer(offer_id)
    Pengguna.objects.select_for_update().get(pk=offer.candidate_id)
    _require_owner(offer, candidate)
    if offer.status != AslabOffer.STATUS_WAITING:
        raise ValidationError('Penawaran tidak lagi menunggu persetujuan.')
    now = timezone.now()
    if now >= offer.deadline:
        raise ValidationError('Penawaran telah kedaluwarsa.')
    previous = replacement.status
    offer.status = AslabOffer.STATUS_ACCEPTED_INCOMPLETE
    offer.responded_at = now
    offer.decline_reason = ''
    offer.save(update_fields=['status', 'responded_at', 'decline_reason'])
    replacement.status = AslabReplacement.STATUS_COMPLETING_DATA
    replacement.save(update_fields=['status', 'updated_at'])
    _audit(replacement, candidate, 'offer_accepted', previous, replacement.status,
           metadata={'offer_id': offer.pk})
    return offer


@transaction.atomic
def decline_offer(*, offer_id, candidate, reason=''):
    replacement, offer = _lock_offer(offer_id)
    Pengguna.objects.select_for_update().get(pk=offer.candidate_id)
    _require_owner(offer, candidate)
    if offer.status != AslabOffer.STATUS_WAITING or timezone.now() >= offer.deadline:
        raise ValidationError('Penawaran tidak lagi menunggu dan belum kedaluwarsa.')
    previous = replacement.status
    offer.status = AslabOffer.STATUS_DECLINED
    offer.responded_at = timezone.now()
    offer.decline_reason = (reason or '').strip()
    offer.save(update_fields=['status', 'responded_at', 'decline_reason'])
    replacement.status = AslabReplacement.STATUS_WAITING_ACTION
    replacement.save(update_fields=['status', 'updated_at'])
    _audit(replacement, candidate, 'offer_declined', previous, replacement.status,
           reason=offer.decline_reason, metadata={'offer_id': offer.pk})
    return offer


@transaction.atomic
def expire_due_offers(*, now=None):
    now = now or timezone.now()
    if timezone.is_naive(now):
        raise ValidationError('Waktu kedaluwarsa harus timezone-aware.')
    ids = list(AslabOffer.objects.filter(
        status=AslabOffer.STATUS_WAITING, deadline__lte=now).order_by('replacement_id', 'pk')
        .values_list('pk', flat=True))
    expired = 0
    for offer_id in ids:
        replacement, offer = _lock_offer(offer_id)
        if offer.status != AslabOffer.STATUS_WAITING or offer.deadline > now:
            continue
        previous = replacement.status
        offer.status = AslabOffer.STATUS_EXPIRED
        offer.save(update_fields=['status'])
        replacement.status = AslabReplacement.STATUS_WAITING_ACTION
        replacement.save(update_fields=['status', 'updated_at'])
        _audit(replacement, None, 'offer_expired', previous, replacement.status,
               metadata={'offer_id': offer.pk, 'expired_at': now.isoformat()})
        expired += 1
    return expired


@transaction.atomic
def submit_offer_registration(*, offer_id, candidate, registration_form):
    """Persist an already validated ReplacementCandidateForm under authoritative row locks."""
    replacement, offer = _lock_offer(offer_id)
    locked_candidate = Pengguna.objects.select_for_update().get(pk=offer.candidate_id)
    _require_owner(offer, candidate)
    if locked_candidate.role != 'mahasiswa' or not locked_candidate.is_verified:
        raise ValidationError('Kandidat harus mahasiswa terverifikasi.')
    if offer.status != AslabOffer.STATUS_ACCEPTED_INCOMPLETE:
        raise ValidationError('Penawaran belum siap menerima data kandidat.')
    if not getattr(registration_form, 'is_bound', False) or not registration_form.is_valid():
        raise ValidationError('Data pendaftaran kandidat belum valid.')
    if registration_form.offer.pk != offer.pk or registration_form.candidate.pk != candidate.pk:
        raise ValidationError('Form pendaftaran tidak sesuai dengan penawaran.')
    registrations = list(PendaftaranAsleb.objects.select_for_update().filter(
        replacement_process=replacement).order_by('pk'))
    existing = next((item for item in registrations if item.pk == offer.registration_id), None)
    if offer.registration_id and existing is None:
        raise ValidationError('Riwayat pendaftaran penawaran tidak ditemukan.')
    if existing and registration_form.instance.pk != existing.pk:
        raise ValidationError('Revisi harus menggunakan pendaftaran yang sudah terhubung.')
    registration = registration_form.save(commit=False)
    registration.pk = existing.pk if existing else None
    registration._state.adding = existing is None
    registration.nama = locked_candidate.nama_pengguna
    registration.nim = locked_candidate.nim_nik
    registration.no_hp = locked_candidate.no_hp
    registration.email = locked_candidate.email
    registration.program_studi = locked_candidate.prodi
    registration.matkul_id = replacement.slot.matkul_id
    registration.periode_id = replacement.slot.periode_id
    registration.jenis = PendaftaranAsleb.JENIS_REPLACEMENT
    registration.replacement_process = replacement
    registration.candidate_user = locked_candidate
    registration.status = 'diajukan'
    try:
        registration.full_clean()
        registration.save()
    except IntegrityError as exc:
        raise ValidationError('Kandidat sudah memiliki pendaftaran penggantian aktif.') from exc
    previous = replacement.status
    now = timezone.now()
    offer.registration = registration
    offer.status = AslabOffer.STATUS_SUBMITTED
    offer.submitted_at = now
    offer.verified_at = None
    offer.verified_by = None
    offer.verification_notes = ''
    offer.save(update_fields=['registration', 'status', 'submitted_at', 'verified_at',
                              'verified_by', 'verification_notes'])
    replacement.status = AslabReplacement.STATUS_WAITING_VERIFICATION
    replacement.save(update_fields=['status', 'updated_at'])
    _audit(replacement, candidate, 'candidate_data_submitted', previous, replacement.status,
           metadata={'offer_id': offer.pk, 'registration_id': registration.pk})
    return registration


@transaction.atomic
def return_offer_for_revision(*, offer_id, actor, notes):
    if not can_manage_lab_operations(actor):
        raise ValidationError('Hanya laboran yang dapat mengembalikan data untuk revisi.')
    notes = (notes or '').strip()
    if not notes:
        raise ValidationError('Catatan revisi wajib diisi.')
    replacement, offer = _lock_offer(offer_id)
    if offer.status != AslabOffer.STATUS_SUBMITTED or not offer.registration_id:
        raise ValidationError('Hanya penawaran yang sudah diajukan yang dapat direvisi.')
    PendaftaranAsleb.objects.select_for_update().get(pk=offer.registration_id)
    previous = replacement.status
    offer.status = AslabOffer.STATUS_ACCEPTED_INCOMPLETE
    offer.submitted_at = None
    offer.verified_at = None
    offer.verified_by = None
    offer.verification_notes = notes
    offer.save(update_fields=['status', 'submitted_at', 'verified_at', 'verified_by',
                              'verification_notes'])
    replacement.status = AslabReplacement.STATUS_COMPLETING_DATA
    replacement.save(update_fields=['status', 'updated_at'])
    _audit(replacement, actor, 'offer_returned_for_revision', previous, replacement.status,
           reason=notes, metadata={'offer_id': offer.pk, 'registration_id': offer.registration_id})
    return offer


def _validate_termination_input(*, actor, reason_type, reason, effective_date, method):
    if not can_manage_lab_operations(actor):
        raise ValidationError('Hanya laboran yang dapat mengakhiri penugasan aslab.')

    normalized_reason = (reason or '').strip()
    if not normalized_reason:
        raise ValidationError('Alasan pengakhiran wajib diisi.')
    if reason_type not in REASON_STATUS_MAP:
        raise ValidationError('Jenis alasan pengakhiran tidak valid.')
    valid_methods = {value for value, _label in AslabReplacement.METHOD_CHOICES}
    if method not in valid_methods:
        raise ValidationError('Metode penggantian tidak valid.')
    if type(effective_date) is not date:
        raise ValidationError('Tanggal efektif tidak valid.')
    return normalized_reason


def _lock_person_termination_state(*, asleb_id, assignment_id=None, require_single_active=False):
    """Lock Asleb, then assignments, slot, and user; future activation must use this order."""
    try:
        asleb = Asleb.objects.select_for_update().get(pk=asleb_id)
    except Asleb.DoesNotExist as exc:
        raise ValidationError('Data Aslab tidak ditemukan.') from exc

    assignments = list(
        AslabAssignment.objects.select_for_update()
        .filter(asleb_id=asleb.pk)
        .order_by('pk')
    )
    if require_single_active:
        active_assignments = [
            item for item in assignments if item.status == AslabAssignment.STATUS_ACTIVE
        ]
        if not active_assignments:
            raise ValidationError(
                'Aslab ini belum memiliki penugasan aktif. Jalankan audit slot sebelum '
                'mengakhiri masa tugas.'
            )
        if len(active_assignments) > 1:
            raise ValidationError(
                'Aslab ini memiliki beberapa penugasan aktif. Silakan pilih mata kuliah/slot '
                'tertentu melalui alur penggantian baru.'
            )
        assignment = active_assignments[0]
    else:
        assignment = next((item for item in assignments if item.pk == assignment_id), None)
        if assignment is None:
            raise ValidationError('Penugasan aslab tidak ditemukan atau sudah berubah.')

    slots = list(
        AslabSlot.objects.select_for_update()
        .filter(pk__in=[assignment.slot_id])
        .order_by('pk')
    )
    if not slots:
        raise ValidationError('Slot penugasan aslab tidak ditemukan.')
    pengguna = (
        Pengguna.objects.select_for_update()
        .filter(nim_nik=asleb.nim)
        .order_by('pk')
        .first()
    )
    return asleb, assignments, assignment, slots[0], pengguna


def _end_locked_assignment(
    *, asleb, assignments, assignment, slot, pengguna, actor, reason_type,
    normalized_reason, effective_date, method,
):
    if assignment.status != AslabAssignment.STATUS_ACTIVE:
        raise ValidationError('Penugasan ini sudah tidak aktif.')
    if not slot.periode.mulai <= effective_date <= slot.periode.selesai:
        raise ValidationError('Tanggal efektif harus berada dalam periode penugasan.')
    if effective_date < assignment.mulai_pada:
        raise ValidationError('Tanggal efektif tidak boleh sebelum tanggal mulai penugasan.')

    assignment.status = REASON_STATUS_MAP[reason_type]
    assignment.berakhir_pada = effective_date
    assignment.alasan_berakhir = normalized_reason
    assignment.diakhiri_oleh = actor
    assignment.save(update_fields=[
        'status', 'berakhir_pada', 'alasan_berakhir', 'diakhiri_oleh', 'diperbarui_pada',
    ])

    slot.status = AslabSlot.STATUS_VACANT
    slot.save(update_fields=['status', 'diperbarui_pada'])

    replacement = AslabReplacement.objects.create(
        slot=slot,
        outgoing_assignment=assignment,
        effective_date=effective_date,
        transfer_month=effective_date.replace(day=1),
        method=method,
        created_by=actor,
    )

    has_other_active = any(
        item.pk != assignment.pk and item.status == AslabAssignment.STATUS_ACTIVE
        for item in assignments
    )
    if not has_other_active:
        if asleb.status != 'nonaktif':
            asleb.status = 'nonaktif'
            asleb.save(update_fields=['status', 'diperbarui_pada'])
        if pengguna and pengguna.role == 'asisten_lab':
            pengguna.role = 'mahasiswa'
            pengguna.save(update_fields=['role', 'diperbarui_pada'])

    AslabReplacementAudit.objects.create(
        replacement=replacement,
        actor=actor,
        action='assignment_ended',
        previous_state=AslabAssignment.STATUS_ACTIVE,
        new_state=assignment.status,
        reason=normalized_reason,
        metadata={
            'reason_type': reason_type,
            'replacement_status': replacement.status,
            'effective_date': effective_date.isoformat(),
        },
    )
    return replacement


@transaction.atomic
def end_assignment_for_replacement(
    *, assignment_id, actor, reason_type, reason, effective_date,
    method=AslabReplacement.METHOD_UNDECIDED,
):
    normalized_reason = _validate_termination_input(
        actor=actor, reason_type=reason_type, reason=reason,
        effective_date=effective_date, method=method,
    )
    asleb_id = (
        AslabAssignment.objects.filter(pk=assignment_id)
        .values_list('asleb_id', flat=True)
        .first()
    )
    if asleb_id is None:
        raise ValidationError('Penugasan aslab tidak ditemukan.')
    state = _lock_person_termination_state(asleb_id=asleb_id, assignment_id=assignment_id)
    return _end_locked_assignment(
        asleb=state[0], assignments=state[1], assignment=state[2], slot=state[3],
        pengguna=state[4], actor=actor, reason_type=reason_type,
        normalized_reason=normalized_reason, effective_date=effective_date, method=method,
    )


@transaction.atomic
def end_single_active_assignment_for_replacement(
    *, asleb_id, actor, reason_type, reason, effective_date,
    method=AslabReplacement.METHOD_UNDECIDED,
):
    normalized_reason = _validate_termination_input(
        actor=actor, reason_type=reason_type, reason=reason,
        effective_date=effective_date, method=method,
    )
    state = _lock_person_termination_state(asleb_id=asleb_id, require_single_active=True)
    return _end_locked_assignment(
        asleb=state[0], assignments=state[1], assignment=state[2], slot=state[3],
        pengguna=state[4], actor=actor, reason_type=reason_type,
        normalized_reason=normalized_reason, effective_date=effective_date, method=method,
    )
