from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.asleb.models import Asleb, HonorAsleb, HonorReassignment
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

PAYMENT_BLOCKING_REPLACEMENT_STATUSES = {
    AslabReplacement.STATUS_WAITING_ACTION,
    AslabReplacement.STATUS_SEARCHING,
    AslabReplacement.STATUS_WAITING_CONSENT,
    AslabReplacement.STATUS_COMPLETING_DATA,
    AslabReplacement.STATUS_WAITING_VERIFICATION,
    AslabReplacement.STATUS_ACTIVE,
}


def with_replacement_hold_state(queryset=None):
    queryset = queryset if queryset is not None else HonorAsleb.objects.all()
    blocking_replacement = AslabReplacement.objects.filter(
        outgoing_assignment__asleb_id=OuterRef('asleb_id'),
        status__in=PAYMENT_BLOCKING_REPLACEMENT_STATUSES,
        transfer_month__lte=OuterRef('bulan'),
        slot__periode__selesai__gte=OuterRef('bulan'),
    )
    return queryset.annotate(replacement_held=Exists(blocking_replacement))


def payment_eligible_honors(queryset=None):
    correction_required = HonorReassignment.objects.filter(
        honor_id=OuterRef('pk'),
        status=HonorReassignment.STATUS_CORRECTION_REQUIRED,
    )
    return with_replacement_hold_state(queryset).annotate(
        replacement_correction_required=Exists(correction_required),
    ).filter(
        replacement_held=False,
        replacement_correction_required=False,
    )


def _lock_replacement_for_honor(replacement):
    try:
        locked_replacement = AslabReplacement.objects.select_for_update().select_related(
            'slot__periode', 'outgoing_assignment',
        ).get(pk=replacement.pk)
    except AslabReplacement.DoesNotExist as exc:
        raise ValidationError('Proses penggantian tidak ditemukan.') from exc

    return locked_replacement


def _lock_honors_for_replacement(locked_replacement, outgoing):
    period_end = locked_replacement.slot.periode.selesai.replace(day=1)
    return list(HonorAsleb.objects.select_for_update().filter(
        asleb=outgoing,
        bulan__gte=locked_replacement.transfer_month,
        bulan__lte=period_end,
    ).order_by('pk'))


@transaction.atomic
def hold_replacement_honor(*, replacement, actor):
    locked_replacement = _lock_replacement_for_honor(replacement)
    outgoing = Asleb.objects.select_for_update().get(
        pk=locked_replacement.outgoing_assignment.asleb_id,
    )
    honors = _lock_honors_for_replacement(locked_replacement, outgoing)
    existing_ids = set(HonorReassignment.objects.select_for_update().filter(
        replacement=locked_replacement,
        honor_id__in=[honor.pk for honor in honors],
    ).order_by('pk').values_list('honor_id', flat=True))
    created = 0
    for honor in honors:
        if honor.pk in existing_ids:
            continue
        HonorReassignment.objects.create(
            replacement=locked_replacement,
            honor=honor,
            bulan=honor.bulan.replace(day=1),
            original_asleb=outgoing,
            final_asleb=None,
            status=HonorReassignment.STATUS_HELD,
            reason='Honor ditahan sampai pengganti diverifikasi dan diaktifkan.',
            acted_by=actor,
        )
        created += 1
    return created


@transaction.atomic
def reassign_replacement_honor(*, replacement, incoming_asleb, actor):
    """Move existing unlocked monthly honor rows and record every decision."""
    locked_replacement = _lock_replacement_for_honor(replacement)
    outgoing_id = locked_replacement.outgoing_assignment.asleb_id
    asleb_ids = sorted({outgoing_id, incoming_asleb.pk})
    locked_aslebs = {
        item.pk: item for item in Asleb.objects.select_for_update().filter(
            pk__in=asleb_ids,
        ).order_by('pk')
    }
    outgoing = locked_aslebs.get(outgoing_id)
    incoming = locked_aslebs.get(incoming_asleb.pk)
    if outgoing is None or incoming is None:
        raise ValidationError('Data aslab asal atau pengganti tidak ditemukan.')
    honors = _lock_honors_for_replacement(locked_replacement, outgoing)

    audits = {
        audit.honor_id: audit
        for audit in HonorReassignment.objects.select_for_update().filter(
            replacement=locked_replacement,
            honor_id__in=[honor.pk for honor in honors],
        ).order_by('pk')
    }
    issued_ids = set(HonorAsleb.objects.filter(
        pk__in=[honor.pk for honor in honors], issued_honor_letters__isnull=False,
    ).values_list('pk', flat=True))
    unlocked = [
        honor for honor in honors
        if honor.status != 'dibayar' and honor.pk not in issued_ids
        and (honor.pk not in audits or audits[honor.pk].status == HonorReassignment.STATUS_HELD)
    ]
    registration = None
    if unlocked:
        registration = PendaftaranAsleb.objects.select_for_update().filter(
            replacement_process=locked_replacement,
            nim=incoming.nim,
            status__in=['diterima', 'digenerate'],
        ).order_by('-pk').first()
        if not registration or not registration.rekening.strip() or not registration.nama_pemilik_rekening.strip():
            raise ValidationError('Data rekening pengganti belum lengkap atau belum terverifikasi.')

    for honor in honors:
        audit = audits.get(honor.pk)
        if audit and audit.status != HonorReassignment.STATUS_HELD:
            continue
        month = honor.bulan.replace(day=1)
        if honor.status == 'dibayar' or honor.pk in issued_ids:
            values = {
                'bulan': month,
                'original_asleb': outgoing,
                'final_asleb': incoming,
                'status': HonorReassignment.STATUS_CORRECTION_REQUIRED,
                'reason': 'Honor sudah dibayar atau masuk surat pembayaran dan memerlukan koreksi manual.',
                'acted_by': actor,
            }
            if audit:
                for field, value in values.items():
                    setattr(audit, field, value)
                audit.save(update_fields=list(values))
            else:
                HonorReassignment.objects.create(
                    replacement=locked_replacement, honor=honor, **values,
                )
            continue
        honor.asleb = incoming
        honor.metode_transfer = registration.metode_rekening
        honor.nomor_transfer = registration.rekening.strip()
        honor.nama_pemilik_transfer = registration.nama_pemilik_rekening.strip()
        honor.save(update_fields=[
            'asleb', 'metode_transfer', 'nomor_transfer', 'nama_pemilik_transfer',
            'level', 'biaya_admin', 'jumlah', 'diperbarui_pada',
        ])
        values = {
            'bulan': month,
            'original_asleb': outgoing,
            'final_asleb': incoming,
            'status': HonorReassignment.STATUS_REASSIGNED,
            'reason': 'Honor dialihkan mulai bulan efektif penggantian aslab.',
            'acted_by': actor,
        }
        if audit:
            for field, value in values.items():
                setattr(audit, field, value)
            audit.save(update_fields=list(values))
        else:
            HonorReassignment.objects.create(
                replacement=locked_replacement, honor=honor, **values,
            )

    statuses = HonorReassignment.objects.filter(
        replacement=locked_replacement,
    ).values_list('status', flat=True)
    return {
        'reassigned': sum(status == HonorReassignment.STATUS_REASSIGNED for status in statuses),
        'correction_required': sum(
            status == HonorReassignment.STATUS_CORRECTION_REQUIRED for status in statuses
        ),
    }


def reconcile_retrospective_honor(*, honor, actor=None):
    """Repair an outgoing honor created after its replacement was activated."""
    if not honor.pk:
        raise ValidationError('Honor harus disimpan sebelum direkonsiliasi.')
    replacement_ids = list(AslabReplacement.objects.filter(
        outgoing_assignment__asleb_id=honor.asleb_id,
        status=AslabReplacement.STATUS_ACTIVE,
        transfer_month__lte=honor.bulan,
        slot__periode__selesai__gte=honor.bulan,
    ).order_by('pk').values_list('pk', flat=True)[:2])
    if not replacement_ids:
        return honor
    if len(replacement_ids) > 1:
        raise ValidationError('Honor cocok dengan lebih dari satu penggantian aktif.')
    replacement = AslabReplacement.objects.select_related(
        'incoming_assignment__asleb', 'activated_by', 'created_by',
    ).get(pk=replacement_ids[0])
    if not replacement.incoming_assignment_id:
        raise ValidationError('Penggantian aktif belum memiliki penugasan pengganti.')
    reassign_replacement_honor(
        replacement=replacement,
        incoming_asleb=replacement.incoming_assignment.asleb,
        actor=actor or replacement.activated_by or replacement.created_by,
    )
    honor.refresh_from_db()
    return honor


def eligible_candidate_queryset(replacement):
    slot = replacement.slot
    assigned_nims = AslabAssignment.objects.filter(
        status=AslabAssignment.STATUS_ACTIVE,
        slot__periode_id=slot.periode_id,
        slot__matkul_id=slot.matkul_id,
    ).values_list('asleb__nim', flat=True)
    conflicting_offers = AslabOffer.objects.filter(
        status__in=AslabOffer.LIVE_STATUSES,
        replacement__slot__periode_id=slot.periode_id,
    ).values_list('candidate_id', flat=True)
    live_registrations = PendaftaranAsleb.objects.filter(
        jenis=PendaftaranAsleb.JENIS_REPLACEMENT,
        status__in=PendaftaranAsleb.LIVE_REPLACEMENT_STATUSES,
        replacement_process__slot__periode_id=slot.periode_id,
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
    slot = AslabSlot.objects.select_for_update().get(pk=replacement.slot_id)
    try:
        offer = AslabOffer.objects.select_for_update().get(
            pk=offer_id, replacement_id=replacement.pk)
    except AslabOffer.DoesNotExist as exc:
        raise ValidationError('Penawaran tidak lagi terkait dengan proses penggantian.') from exc
    replacement.slot = slot
    offer.replacement = replacement
    return replacement, slot, offer


OFFER_TRANSITION_PARENT_STATES = {
    'accept': AslabReplacement.STATUS_WAITING_CONSENT,
    'decline': AslabReplacement.STATUS_WAITING_CONSENT,
    'expire': AslabReplacement.STATUS_WAITING_CONSENT,
    'submit': AslabReplacement.STATUS_COMPLETING_DATA,
    'return': AslabReplacement.STATUS_WAITING_VERIFICATION,
}


def _validate_offer_transition(*, replacement, slot, transition):
    expected = OFFER_TRANSITION_PARENT_STATES[transition]
    if replacement.status != expected or slot.status != AslabSlot.STATUS_VACANT:
        raise ValidationError(
            'Proses tidak dapat melanjutkan transisi penawaran karena parent atau slot sudah berubah.'
        )


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
    try:
        candidate = Pengguna.objects.select_for_update().get(pk=candidate_id)
    except Pengguna.DoesNotExist as exc:
        raise ValidationError('Kandidat tidak ditemukan.') from exc
    if replacement.status not in {
        AslabReplacement.STATUS_WAITING_ACTION,
        AslabReplacement.STATUS_SEARCHING,
    }:
        raise ValidationError('Status proses penggantian tidak dapat menerima penawaran baru.')
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
    replacement, slot, offer = _lock_offer(offer_id)
    Pengguna.objects.select_for_update().get(pk=offer.candidate_id)
    _require_owner(offer, candidate)
    _validate_offer_transition(
        replacement=replacement, slot=slot, transition='accept')
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
    replacement, slot, offer = _lock_offer(offer_id)
    Pengguna.objects.select_for_update().get(pk=offer.candidate_id)
    _require_owner(offer, candidate)
    _validate_offer_transition(
        replacement=replacement, slot=slot, transition='decline')
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


def expire_due_offers(*, now=None):
    now = now or timezone.now()
    if timezone.is_naive(now):
        raise ValidationError('Waktu kedaluwarsa harus timezone-aware.')
    ids = list(AslabOffer.objects.filter(
        status=AslabOffer.STATUS_WAITING, deadline__lte=now).order_by('replacement_id', 'pk')
        .values_list('pk', flat=True))
    expired = 0
    for offer_id in ids:
        expired += int(_expire_due_offer(offer_id=offer_id, now=now))
    return expired


@transaction.atomic
def _expire_due_offer(*, offer_id, now):
    replacement, slot, offer = _lock_offer(offer_id)
    if (
        replacement.status != OFFER_TRANSITION_PARENT_STATES['expire']
        or slot.status != AslabSlot.STATUS_VACANT
        or offer.status != AslabOffer.STATUS_WAITING
        or offer.deadline > now
    ):
        return False
    previous = replacement.status
    offer.status = AslabOffer.STATUS_EXPIRED
    offer.save(update_fields=['status'])
    replacement.status = AslabReplacement.STATUS_WAITING_ACTION
    replacement.save(update_fields=['status', 'updated_at'])
    _audit(replacement, None, 'offer_expired', previous, replacement.status,
           metadata={'offer_id': offer.pk, 'expired_at': now.isoformat()})
    return True


@transaction.atomic
def submit_offer_registration(*, offer_id, candidate, registration_form):
    """Rebind raw form input to locked workflow rows, validate, then persist it."""
    from .replacement_forms import ReplacementCandidateForm

    replacement, slot, offer = _lock_offer(offer_id)
    locked_candidate = Pengguna.objects.select_for_update().get(pk=offer.candidate_id)
    _require_owner(offer, candidate)
    _validate_offer_transition(
        replacement=replacement, slot=slot, transition='submit')
    if locked_candidate.role != 'mahasiswa' or not locked_candidate.is_verified:
        raise ValidationError('Kandidat harus mahasiswa terverifikasi.')
    if offer.status != AslabOffer.STATUS_ACCEPTED_INCOMPLETE:
        raise ValidationError('Penawaran belum siap menerima data kandidat.')
    if (
        not isinstance(registration_form, ReplacementCandidateForm)
        or not registration_form.is_bound
        or registration_form.offer.pk != offer.pk
        or registration_form.candidate.pk != candidate.pk
    ):
        raise ValidationError('Form pendaftaran tidak sesuai dengan penawaran.')
    registrations = list(PendaftaranAsleb.objects.select_for_update().filter(
        replacement_process=replacement).order_by('pk'))
    existing = next((item for item in registrations if item.pk == offer.registration_id), None)
    if offer.registration_id and existing is None:
        raise ValidationError('Riwayat pendaftaran penawaran tidak ditemukan.')
    if existing and registration_form.instance.pk != existing.pk:
        raise ValidationError('Revisi harus menggunakan pendaftaran yang sudah terhubung.')
    if not existing and registration_form.instance.pk:
        raise ValidationError('Pendaftaran baru tidak boleh menggunakan instance yang sudah ada.')
    canonical_form = ReplacementCandidateForm(
        data=registration_form.data,
        files=registration_form.files,
        offer=offer,
        candidate=locked_candidate,
        instance=existing,
    )
    if not canonical_form.is_valid():
        raise ValidationError('Data pendaftaran kandidat belum valid.')
    registration = canonical_form.save(commit=False)
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
    replacement, slot, offer = _lock_offer(offer_id)
    _validate_offer_transition(
        replacement=replacement, slot=slot, transition='return')
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
    hold_replacement_honor(replacement=replacement, actor=actor)

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
