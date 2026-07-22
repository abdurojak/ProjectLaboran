from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.asleb.models import Asleb
from apps.core.permissions import can_manage_lab_operations
from apps.pengguna.models import Pengguna

from .models import AslabAssignment, AslabReplacement, AslabReplacementAudit, AslabSlot


REASON_STATUS_MAP = {
    'resignation': AslabAssignment.STATUS_RESIGNED,
    'dismissal': AslabAssignment.STATUS_TERMINATED,
    'other': AslabAssignment.STATUS_TERMINATED,
}


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
