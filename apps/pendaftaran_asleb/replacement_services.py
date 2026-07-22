from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.permissions import can_manage_lab_operations
from apps.pengguna.models import Pengguna

from .models import AslabAssignment, AslabReplacement, AslabReplacementAudit, AslabSlot


REASON_STATUS_MAP = {
    'resignation': AslabAssignment.STATUS_RESIGNED,
    'dismissal': AslabAssignment.STATUS_TERMINATED,
    'other': AslabAssignment.STATUS_TERMINATED,
}


@transaction.atomic
def end_assignment_for_replacement(
    *, assignment_id, actor, reason_type, reason, effective_date,
    method=AslabReplacement.METHOD_UNDECIDED,
):
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
    if not isinstance(effective_date, date):
        raise ValidationError('Tanggal efektif tidak valid.')

    try:
        assignment = AslabAssignment.objects.select_for_update().select_related(
            'slot__periode', 'asleb',
        ).get(pk=assignment_id)
    except AslabAssignment.DoesNotExist as exc:
        raise ValidationError('Penugasan aslab tidak ditemukan.') from exc

    slot = AslabSlot.objects.select_for_update().select_related('periode').get(pk=assignment.slot_id)
    asleb = assignment.asleb.__class__.objects.select_for_update().get(pk=assignment.asleb_id)
    pengguna = Pengguna.objects.select_for_update().filter(nim_nik=asleb.nim).first()

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

    has_other_active = AslabAssignment.objects.select_for_update().filter(
        asleb=asleb,
        status=AslabAssignment.STATUS_ACTIVE,
    ).exclude(pk=assignment.pk).exists()
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
        new_state=replacement.status,
        reason=normalized_reason,
        metadata={
            'reason_type': reason_type,
            'assignment_status': assignment.status,
            'effective_date': effective_date.isoformat(),
        },
    )
    return replacement
