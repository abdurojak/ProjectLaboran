# Aslab Replacement Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe, auditable workflow for ending an aslab assignment and filling the same course slot through a consent-based direct offer or limited registration, with monthly honor reassignment and no loss of historical activity.

**Architecture:** Keep `Asleb` as the existing person/access record and add assignment, slot, replacement, offer, and targeted-opening records in `pendaftaran_asleb`. All state changes go through transactional domain services with row locks. Existing regular registration remains the default path; replacement records are additive and the old manual end endpoint delegates to the new workflow.

**Tech Stack:** Django 4.2, MySQL, Django templates, existing `Pengguna` session middleware, Django transactions/constraints, unittest-style Django `TestCase` and `TransactionTestCase`.

---

## Compatibility Boundaries

- Do not alter the public regular-registration URL or its open/closed calculation.
- Do not rewrite completed attendance, grades, reports, or historical schedule records.
- Do not change end-of-period experience behavior except where an assignment is explicitly ended early.
- Do not add an aslab foreign key to `JadwalPraktikum`; existing course-based schedule resolution remains in place.
- Do not delete an `Asleb` that has honor, attendance, reports, reminders, or assignment history.
- Preserve old `PendaftaranAsleb` rows and make replacement fields nullable with regular defaults.
- Run focused tests after every task and the full suite before release.

## File Map

- `apps/pendaftaran_asleb/models.py`: slot, assignment, replacement, offer, targeted opening, audit, and registration linkage.
- `apps/pendaftaran_asleb/replacement_services.py`: transactional state transitions, role changes, activation, and monthly honor reassignment.
- `apps/pendaftaran_asleb/replacement_forms.py`: termination, offer, limited opening, candidate submission, and verification forms.
- `apps/pendaftaran_asleb/replacement_views.py`: laboran and student replacement screens.
- `apps/pendaftaran_asleb/replacement_notifications.py`: after-commit notification payloads and email wrappers.
- `apps/pendaftaran_asleb/urls.py`: replacement routes without changing existing registration routes.
- `apps/pendaftaran_asleb/admin.py`: read-oriented administration for new records.
- `apps/pendaftaran_asleb/test_replacement_models.py`: constraints and migration-compatible model behavior.
- `apps/pendaftaran_asleb/test_replacement_services.py`: transitions, concurrency guards, roles, honor, and experience.
- `apps/pendaftaran_asleb/test_replacement_views.py`: authorization and complete web workflows.
- `apps/pendaftaran_asleb/templates/pendaftaran_asleb/replacement_*.html`: laboran and student workflow UI.
- `apps/asleb/views.py`: delegate old termination and guard destructive deletion.
- `apps/asleb/templates/asleb/asleb_list.html`: replace the prompt action with the workflow link and status.
- `apps/asleb/models.py`: honor reassignment audit reference and safe delete protection only if required by generated migration.
- `apps/asleb/tests.py`: regression coverage for existing list, honor, attendance, and delete behavior.

### Task 1: Establish Regression Baseline

**Files:**
- Modify: `apps/asleb/tests.py`
- Modify: `apps/pendaftaran_asleb/tests.py`

- [ ] **Step 1: Run the existing focused suites before changing behavior**

Run:

```powershell
python manage.py test apps.asleb apps.pendaftaran_asleb apps.jadwal --keepdb
```

Expected: PASS. Record any pre-existing failure in the implementation log and do not disguise it as a feature regression.

- [ ] **Step 2: Add tests that lock existing registration and historical-data behavior**

Add tests equivalent to:

```python
def test_regular_registration_still_uses_current_period(self):
    form = PendaftaranAslebForm(data=self.valid_registration_data())
    self.assertTrue(form.is_valid(), form.errors)
    registration = form.save()
    self.assertEqual(registration.periode, PeriodeAsleb.get_for_date(timezone.localdate()))

def test_manual_deactivation_does_not_delete_completed_activity(self):
    attendance = AbsensiMasukAsleb.objects.create(
        asleb=self.asleb,
        jadwal=self.jadwal,
        tanggal_absensi=timezone.localdate(),
        foto_absensi=self.sample_image(),
    )
    deactivate_asleb_membership(self.asleb, forced=True, reason='Mengundurkan diri')
    self.assertTrue(AbsensiMasukAsleb.objects.filter(pk=attendance.pk).exists())
```

- [ ] **Step 3: Run the new baseline tests**

Run:

```powershell
python manage.py test apps.asleb.tests.AslebViewTests apps.pendaftaran_asleb.tests.PendaftaranAslebViewTests --keepdb
```

Expected: PASS. These tests establish behavior that every later task must preserve.

- [ ] **Step 4: Commit the regression contract**

```powershell
git add apps/asleb/tests.py apps/pendaftaran_asleb/tests.py
git commit -m "test: lock aslab replacement compatibility"
```

### Task 2: Add Slot and Assignment Models

**Files:**
- Modify: `apps/pendaftaran_asleb/models.py`
- Create: `apps/pendaftaran_asleb/migrations/0016_aslab_assignment_foundation.py`
- Create: `apps/pendaftaran_asleb/test_replacement_models.py`
- Modify: `apps/pendaftaran_asleb/admin.py`

- [ ] **Step 1: Write failing model constraint tests**

Create tests for two slots and one active occupant:

```python
class AslabSlotConstraintTests(TestCase):
    def test_course_period_allows_only_slot_one_and_two(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AslabSlot.objects.create(
                    periode=self.period,
                    matkul=self.course,
                    nomor=3,
                )

    def test_only_one_active_assignment_per_slot(self):
        AslabAssignment.objects.create(
            slot=self.slot,
            asleb=self.first_asleb,
            mulai_pada=self.period.mulai,
            status=AslabAssignment.STATUS_ACTIVE,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AslabAssignment.objects.create(
                    slot=self.slot,
                    asleb=self.second_asleb,
                    mulai_pada=self.period.mulai,
                    status=AslabAssignment.STATUS_ACTIVE,
                )
```

- [ ] **Step 2: Run model tests and verify missing-model failures**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_models -v 2
```

Expected: FAIL because `AslabSlot` and `AslabAssignment` do not exist.

- [ ] **Step 3: Add the foundation models with database constraints**

Add models following this interface:

```python
class AslabSlot(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_VACANT = 'vacant'
    STATUS_CLOSED = 'closed'
    periode = models.ForeignKey(PeriodeAsleb, on_delete=models.PROTECT, related_name='aslab_slots')
    matkul = models.ForeignKey(MataKuliahAsleb, on_delete=models.PROTECT, related_name='aslab_slots')
    nomor = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=12, default=STATUS_ACTIVE, choices=[
        (STATUS_ACTIVE, 'Aktif'), (STATUS_VACANT, 'Kosong'), (STATUS_CLOSED, 'Ditutup'),
    ])
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(nomor__in=[1, 2]), name='aslab_slot_number_1_or_2'),
            models.UniqueConstraint(fields=['periode', 'matkul', 'nomor'], name='unique_aslab_slot'),
        ]


class AslabAssignment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_RESIGNED = 'resigned'
    STATUS_TERMINATED = 'terminated'
    STATUS_REPLACED = 'replaced'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    slot = models.ForeignKey(AslabSlot, on_delete=models.PROTECT, related_name='assignments')
    asleb = models.ForeignKey('asleb.Asleb', on_delete=models.PROTECT, related_name='assignments')
    source_pendaftaran = models.ForeignKey(
        'PendaftaranAsleb', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='aslab_assignments',
    )
    mulai_pada = models.DateField()
    berakhir_pada = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16)
    alasan_berakhir = models.TextField(blank=True)
    diakhiri_oleh = models.ForeignKey(
        'pengguna.Pengguna', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='aslab_assignments_ended',
    )
    menggantikan = models.OneToOneField(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='digantikan_oleh',
    )
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['slot'], condition=models.Q(status='active'),
                name='unique_active_assignment_per_slot',
            ),
        ]
```

Use `PROTECT` for slot, course, period, and aslab references so operational history cannot cascade away.

- [ ] **Step 4: Generate and inspect the migration**

Run:

```powershell
python manage.py makemigrations pendaftaran_asleb --name aslab_assignment_foundation
python manage.py sqlmigrate pendaftaran_asleb 0016
```

Expected: migration creates both tables and all three constraints without dropping existing columns.

- [ ] **Step 5: Register read-oriented admin classes and run tests**

Admin configuration must show period, course, slot, person, status, and dates, and use `list_select_related`.

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_models -v 2
python manage.py check
```

Expected: PASS.

- [ ] **Step 6: Commit the assignment foundation**

```powershell
git add apps/pendaftaran_asleb/models.py apps/pendaftaran_asleb/migrations/0016_aslab_assignment_foundation.py apps/pendaftaran_asleb/test_replacement_models.py apps/pendaftaran_asleb/admin.py
git commit -m "feat: add aslab assignment slots"
```

### Task 3: Migrate Existing Active Aslab Safely

**Files:**
- Create: `apps/pendaftaran_asleb/migrations/0017_backfill_aslab_assignments.py`
- Create: `apps/pendaftaran_asleb/management/commands/audit_aslab_slots.py`
- Modify: `apps/pendaftaran_asleb/test_replacement_models.py`

- [ ] **Step 1: Add migration tests for unambiguous and ambiguous legacy records**

Test that matching uses period plus accepted/generated registration and never guesses more than two occupants:

```python
def test_backfill_creates_slot_from_matching_registration(self):
    call_command('audit_aslab_slots')
    assignment = AslabAssignment.objects.get(asleb=self.asleb)
    self.assertEqual(assignment.slot.periode, self.period)
    self.assertEqual(assignment.slot.matkul, self.course)

def test_audit_reports_unmatched_legacy_asleb(self):
    output = StringIO()
    call_command('audit_aslab_slots', stdout=output)
    self.assertIn(self.asleb.nim, output.getvalue())
```

- [ ] **Step 2: Run tests and verify they fail before the command/migration exists**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_models.AslabBackfillTests -v 2
```

Expected: FAIL with unknown command or missing assignments. Use the actual class spelling `AslabBackfillTests` in code and command.

- [ ] **Step 3: Implement deterministic backfill**

The migration algorithm must:

```python
for asleb in Asleb.objects.filter(status='aktif', periode_aktif__isnull=False).iterator():
    registrations = PendaftaranAsleb.objects.filter(
        nim=asleb.nim,
        periode_id=asleb.periode_aktif_id,
        status__in=['diterima', 'digenerate'],
    ).select_related('matkul').order_by('matkul_id', 'pk')
    # Create at most one assignment for each exact period/course match.
    # Allocate the lowest free slot number in [1, 2].
    # Leave unmatched or over-capacity rows untouched and report them.
```

Because migrations cannot reliably emit an operational report later, the audit command repeats the read-only matching analysis and exits nonzero with `--strict` when unresolved rows exist.

- [ ] **Step 4: Run migration and audit tests**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_models -v 2
python manage.py audit_aslab_slots
```

Expected: tests PASS; local development data either reports zero unresolved rows or prints their NIMs without modifying them.

- [ ] **Step 5: Commit the safe backfill**

```powershell
git add apps/pendaftaran_asleb/migrations/0017_backfill_aslab_assignments.py apps/pendaftaran_asleb/management/commands/audit_aslab_slots.py apps/pendaftaran_asleb/test_replacement_models.py
git commit -m "feat: backfill aslab assignment slots"
```

### Task 4: Add Replacement, Offer, Opening, and Audit Models

**Files:**
- Modify: `apps/pendaftaran_asleb/models.py`
- Create: `apps/pendaftaran_asleb/migrations/0018_aslab_replacement_workflow.py`
- Modify: `apps/pendaftaran_asleb/test_replacement_models.py`
- Modify: `apps/pendaftaran_asleb/admin.py`

- [ ] **Step 1: Add failing tests for one live process and one live offer**

```python
def test_only_one_open_replacement_per_outgoing_assignment(self):
    AslabReplacement.objects.create(
        slot=self.slot,
        outgoing_assignment=self.assignment,
        effective_date=self.today,
        transfer_month=self.today.replace(day=1),
        status=AslabReplacement.STATUS_WAITING_ACTION,
    )
    with self.assertRaises(IntegrityError):
        with transaction.atomic():
            AslabReplacement.objects.create(
                slot=self.slot,
                outgoing_assignment=self.assignment,
                effective_date=self.today,
                transfer_month=self.today.replace(day=1),
                status=AslabReplacement.STATUS_WAITING_ACTION,
            )

def test_only_one_live_offer_per_replacement(self):
    AslabOffer.objects.create(replacement=self.replacement, candidate=self.student, deadline=self.deadline)
    with self.assertRaises(IntegrityError):
        with transaction.atomic():
            AslabOffer.objects.create(replacement=self.replacement, candidate=self.other_student, deadline=self.deadline)

def test_existing_registration_defaults_to_regular(self):
    registration = PendaftaranAsleb.objects.create(**self.regular_registration_values())
    self.assertEqual(registration.jenis, PendaftaranAsleb.JENIS_REGULER)
    self.assertIsNone(registration.replacement_process_id)
```

- [ ] **Step 2: Run tests and verify missing-model failures**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_models.AslabReplacementModelTests -v 2
```

Expected: FAIL. Use `AslabReplacementModelTests` as the actual class name.

- [ ] **Step 3: Add workflow models and nullable registration linkage**

Implement:

```python
class AslabReplacement(models.Model):
    STATUS_WAITING_ACTION = 'waiting_action'
    STATUS_SEARCHING = 'searching'
    STATUS_WAITING_CONSENT = 'waiting_consent'
    STATUS_COMPLETING_DATA = 'completing_data'
    STATUS_WAITING_VERIFICATION = 'waiting_verification'
    STATUS_ACTIVE = 'active'
    STATUS_CANCELLED = 'cancelled'
    METHOD_UNDECIDED = 'undecided'
    METHOD_DIRECT = 'direct_offer'
    METHOD_LIMITED = 'limited_registration'
    slot = models.ForeignKey(AslabSlot, on_delete=models.PROTECT, related_name='replacements')
    outgoing_assignment = models.OneToOneField(AslabAssignment, on_delete=models.PROTECT, related_name='replacement_process')
    incoming_assignment = models.OneToOneField(AslabAssignment, on_delete=models.PROTECT, null=True, blank=True, related_name='activation_process')
    effective_date = models.DateField()
    transfer_month = models.DateField()
    method = models.CharField(max_length=24, default=METHOD_UNDECIDED)
    status = models.CharField(max_length=32, default=STATUS_WAITING_ACTION)
    created_by = models.ForeignKey('pengguna.Pengguna', on_delete=models.PROTECT, related_name='created_aslab_replacements')
    activated_by = models.ForeignKey('pengguna.Pengguna', on_delete=models.SET_NULL, null=True, blank=True, related_name='activated_aslab_replacements')
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)


class AslabOffer(models.Model):
    LIVE_STATUSES = ['waiting', 'accepted_incomplete', 'submitted']
    replacement = models.ForeignKey(AslabReplacement, on_delete=models.PROTECT, related_name='offers')
    candidate = models.ForeignKey('pengguna.Pengguna', on_delete=models.PROTECT, related_name='aslab_offers')
    registration = models.OneToOneField('PendaftaranAsleb', on_delete=models.SET_NULL, null=True, blank=True, related_name='replacement_offer')
    status = models.CharField(max_length=24, default='waiting')
    deadline = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey('pengguna.Pengguna', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_aslab_offers')
    verification_notes = models.TextField(blank=True)


class LimitedReplacementOpening(models.Model):
    replacement = models.OneToOneField(AslabReplacement, on_delete=models.PROTECT, related_name='limited_opening')
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()
    program_studi = models.CharField(max_length=120, blank=True)
    cohort = models.PositiveSmallIntegerField(null=True, blank=True)
    allowed_candidates = models.ManyToManyField(
        'pengguna.Pengguna', blank=True,
        related_name='allowed_aslab_replacement_openings',
    )
    additional_requirements = models.TextField(blank=True)
    status = models.CharField(max_length=12, default='draft')


class AslabReplacementAudit(models.Model):
    replacement = models.ForeignKey(AslabReplacement, on_delete=models.PROTECT, related_name='audit_entries')
    actor = models.ForeignKey('pengguna.Pengguna', on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=60)
    previous_state = models.CharField(max_length=32, blank=True)
    new_state = models.CharField(max_length=32)
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

Add nullable `jenis`, `replacement_process`, and `candidate_user` fields to `PendaftaranAsleb`, with `jenis='reguler'` as the default. Add conditional unique constraints for live offers and live replacement registrations using explicit status values rather than Python constants inside the migration.

- [ ] **Step 4: Generate migration, inspect SQL, and run tests**

Run:

```powershell
python manage.py makemigrations pendaftaran_asleb --name aslab_replacement_workflow
python manage.py sqlmigrate pendaftaran_asleb 0018
python manage.py test apps.pendaftaran_asleb.test_replacement_models -v 2
python manage.py check
```

Expected: PASS; no non-null column is added to existing registration rows without a default.

- [ ] **Step 5: Commit the workflow schema**

```powershell
git add apps/pendaftaran_asleb/models.py apps/pendaftaran_asleb/migrations/0018_aslab_replacement_workflow.py apps/pendaftaran_asleb/test_replacement_models.py apps/pendaftaran_asleb/admin.py
git commit -m "feat: add aslab replacement workflow records"
```

### Task 5: Implement Transactional Termination

**Files:**
- Create: `apps/pendaftaran_asleb/replacement_services.py`
- Create: `apps/pendaftaran_asleb/test_replacement_services.py`
- Modify: `apps/asleb/views.py`
- Modify: `apps/asleb/tests.py`

- [ ] **Step 1: Write failing termination service tests**

Cover required reason, role downgrade, other active assignments, no experience, slot vacancy, and idempotency:

```python
def test_end_assignment_demotes_user_and_opens_replacement(self):
    result = end_assignment_for_replacement(
        assignment_id=self.assignment.pk,
        actor=self.laboran,
        reason_type='resignation',
        reason='Tidak dapat melanjutkan tugas',
        effective_date=date(2026, 10, 15),
    )
    self.assignment.refresh_from_db()
    self.slot.refresh_from_db()
    self.student.refresh_from_db()
    self.assertEqual(self.assignment.status, AslabAssignment.STATUS_RESIGNED)
    self.assertEqual(self.slot.status, AslabSlot.STATUS_VACANT)
    self.assertEqual(self.student.role, 'mahasiswa')
    self.assertEqual(result.transfer_month, date(2026, 10, 1))
    self.assertFalse(PengalamanPengguna.objects.filter(pengguna=self.student).exists())
```

- [ ] **Step 2: Run service tests and verify failure**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_services.TerminationServiceTests -v 2
```

Expected: FAIL because the service does not exist.

- [ ] **Step 3: Implement the locked transaction**

Use this public interface:

```python
@transaction.atomic
def end_assignment_for_replacement(*, assignment_id, actor, reason_type, reason, effective_date, method='undecided'):
    assignment = AslabAssignment.objects.select_for_update().select_related(
        'slot', 'asleb', 'slot__periode', 'slot__matkul',
    ).get(pk=assignment_id)
    if assignment.status != AslabAssignment.STATUS_ACTIVE:
        raise ValidationError('Penugasan ini sudah tidak aktif.')
    if not reason.strip():
        raise ValidationError('Alasan pengakhiran wajib diisi.')
    if not assignment.slot.periode.mulai <= effective_date <= assignment.slot.periode.selesai:
        raise ValidationError('Tanggal efektif harus berada dalam periode penugasan.')

    end_status = (
        AslabAssignment.STATUS_RESIGNED
        if reason_type == 'resignation'
        else AslabAssignment.STATUS_TERMINATED
    )
    assignment.status = end_status
    assignment.berakhir_pada = effective_date
    assignment.alasan_berakhir = reason.strip()
    assignment.diakhiri_oleh = actor
    assignment.save(update_fields=[
        'status', 'berakhir_pada', 'alasan_berakhir',
        'diakhiri_oleh', 'diperbarui_pada',
    ])
    assignment.slot.status = AslabSlot.STATUS_VACANT
    assignment.slot.save(update_fields=['status', 'diperbarui_pada'])
    replacement = AslabReplacement.objects.create(
        slot=assignment.slot,
        outgoing_assignment=assignment,
        effective_date=effective_date,
        transfer_month=effective_date.replace(day=1),
        method=method,
        created_by=actor,
    )
    _sync_aslab_person_access(assignment.asleb)
    _write_audit(replacement, actor, 'assignment_ended', '', replacement.status, reason)
    return replacement
```

`_sync_aslab_person_access` sets the person record and user role inactive only when no other active assignment exists. It must not call experience creation.

- [ ] **Step 4: Make the old endpoint delegate without breaking its URL**

Keep `asleb:asleb_end_membership` temporarily for compatibility, resolve the active assignment, call the new service, and redirect to the new replacement detail. If no assignment exists for legacy data, show a safe error instructing the laboran to run the slot audit instead of falling back to destructive updates.

- [ ] **Step 5: Run service and existing aslab tests**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_services.TerminationServiceTests apps.asleb.tests.AslebViewTests --keepdb -v 2
```

Expected: PASS, including existing permission checks and no-experience assertions.

- [ ] **Step 6: Commit termination behavior**

```powershell
git add apps/pendaftaran_asleb/replacement_services.py apps/pendaftaran_asleb/test_replacement_services.py apps/asleb/views.py apps/asleb/tests.py
git commit -m "feat: terminate aslab assignments safely"
```

### Task 6: Implement Direct Offers and Candidate Consent

**Files:**
- Create: `apps/pendaftaran_asleb/replacement_forms.py`
- Modify: `apps/pendaftaran_asleb/replacement_services.py`
- Modify: `apps/pendaftaran_asleb/test_replacement_services.py`

- [ ] **Step 1: Write failing offer transition tests**

```python
def test_direct_offer_does_not_promote_candidate_before_verification(self):
    offer = create_direct_offer(
        replacement_id=self.replacement.pk,
        candidate_id=self.candidate.pk,
        deadline=timezone.now() + timedelta(days=3),
        actor=self.laboran,
    )
    accept_offer(offer_id=offer.pk, candidate=self.candidate)
    self.candidate.refresh_from_db()
    self.assertEqual(self.candidate.role, 'mahasiswa')
    self.assertEqual(offer.refresh_from_db().status, AslabOffer.STATUS_ACCEPTED_INCOMPLETE)

def test_expired_offer_cannot_be_accepted(self):
    self.offer.deadline = timezone.now() - timedelta(seconds=1)
    self.offer.save(update_fields=['deadline'])
    with self.assertRaises(ValidationError):
        accept_offer(offer_id=self.offer.pk, candidate=self.candidate)
```

- [ ] **Step 2: Run tests and verify transition failures**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_services.OfferServiceTests -v 2
```

Expected: FAIL because offer services are missing.

- [ ] **Step 3: Implement offer services and forms**

Public service interfaces:

```python
create_direct_offer(*, replacement_id, candidate_id, deadline, actor) -> AslabOffer
accept_offer(*, offer_id, candidate) -> AslabOffer
decline_offer(*, offer_id, candidate, reason='') -> AslabOffer
expire_due_offers(*, now=None) -> int
submit_offer_registration(*, offer_id, candidate, cleaned_data, files) -> PendaftaranAsleb
return_offer_for_revision(*, offer_id, actor, notes) -> AslabOffer
```

Candidate validation requires `role='mahasiswa'`, `is_verified=True`, matching account identity, no active assignment in the same slot, and no other live offer for that candidate/period. `DirectOfferForm` defaults the deadline to three days but permits laboran adjustment.

`ReplacementCandidateForm` subclasses the existing public registration form, fixes `matkul` and `periode` from the slot, writes `jenis='pengganti'`, and rejects attempts to alter those hidden values.

- [ ] **Step 4: Run service and regular-form regression tests**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_services.OfferServiceTests apps.pendaftaran_asleb.tests.PendaftaranAslebViewTests --keepdb -v 2
```

Expected: PASS; regular registration still uses its original form and open/closed rules.

- [ ] **Step 5: Commit direct offer domain logic**

```powershell
git add apps/pendaftaran_asleb/replacement_forms.py apps/pendaftaran_asleb/replacement_services.py apps/pendaftaran_asleb/test_replacement_services.py
git commit -m "feat: add consent based aslab offers"
```

### Task 7: Implement Monthly Honor Hold and Reassignment

**Files:**
- Modify: `apps/asleb/models.py`
- Create: `apps/asleb/migrations/0027_honor_reassignment_audit.py`
- Modify: `apps/pendaftaran_asleb/replacement_services.py`
- Modify: `apps/pendaftaran_asleb/test_replacement_services.py`
- Modify: `apps/asleb/views.py`

- [ ] **Step 1: Write failing whole-month honor tests**

```python
def test_activation_reassigns_effective_month_but_keeps_prior_month(self):
    september = self.create_honor(self.outgoing, date(2026, 9, 1))
    october = self.create_honor(self.outgoing, date(2026, 10, 1))
    activate_replacement(self.offer.pk, actor=self.laboran, active_date=date(2026, 11, 5))
    september.refresh_from_db()
    october.refresh_from_db()
    self.assertEqual(september.asleb, self.outgoing)
    self.assertEqual(october.asleb, self.incoming)

def test_locked_honor_creates_correction_instead_of_rewriting(self):
    honor = self.create_honor(self.outgoing, date(2026, 10, 1), status='dibayar')
    activate_replacement(self.offer.pk, actor=self.laboran, active_date=date(2026, 11, 5))
    honor.refresh_from_db()
    self.assertEqual(honor.asleb, self.outgoing)
    self.assertTrue(HonorReassignment.objects.filter(honor=honor, status='correction_required').exists())
```

- [ ] **Step 2: Run honor tests and verify failure**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_services.HonorReassignmentTests -v 2
```

Expected: FAIL because hold/audit models and activation do not exist.

- [ ] **Step 3: Add honor reassignment audit and hold state**

Add:

```python
class HonorReassignment(models.Model):
    STATUS_HELD = 'held'
    STATUS_REASSIGNED = 'reassigned'
    STATUS_CORRECTION_REQUIRED = 'correction_required'
    replacement = models.ForeignKey('pendaftaran_asleb.AslabReplacement', on_delete=models.PROTECT, related_name='honor_reassignments')
    honor = models.ForeignKey(HonorAsleb, on_delete=models.PROTECT, null=True, blank=True, related_name='reassignment_audits')
    bulan = models.DateField()
    original_asleb = models.ForeignKey(Asleb, on_delete=models.PROTECT, related_name='outgoing_honor_reassignments')
    final_asleb = models.ForeignKey(Asleb, on_delete=models.PROTECT, null=True, blank=True, related_name='incoming_honor_reassignments')
    status = models.CharField(max_length=24)
    reason = models.TextField()
    acted_by = models.ForeignKey('pengguna.Pengguna', on_delete=models.SET_NULL, null=True, blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['replacement', 'honor'], name='unique_replacement_honor_audit'),
        ]
```

Use audit rows for existing honor records. A replacement with no honor row yet is represented by the replacement's transfer month and dashboard state, not by fabricating zero-value `HonorAsleb` rows.

- [ ] **Step 4: Implement idempotent month-based reassignment**

```python
def reassign_replacement_honor(*, replacement, incoming_asleb, actor):
    honors = HonorAsleb.objects.select_for_update().filter(
        asleb=replacement.outgoing_assignment.asleb,
        bulan__gte=replacement.transfer_month,
        bulan__lte=replacement.slot.periode.selesai.replace(day=1),
    )
    for honor in honors:
        if honor.status == 'dibayar':
            HonorReassignment.objects.update_or_create(
                replacement=replacement,
                honor=honor,
                defaults={'bulan': honor.bulan.replace(day=1), 'original_asleb': honor.asleb,
                          'final_asleb': incoming_asleb, 'status': 'correction_required',
                          'reason': 'Honor sudah terkunci/dibayar.', 'acted_by': actor},
            )
            continue
        original = honor.asleb
        honor.asleb = incoming_asleb
        honor.save()
        HonorReassignment.objects.update_or_create(
            replacement=replacement, honor=honor,
            defaults={'bulan': honor.bulan.replace(day=1), 'original_asleb': original,
                      'final_asleb': incoming_asleb, 'status': 'reassigned',
                      'reason': 'Pengalihan honor pergantian aslab.', 'acted_by': actor},
        )
```

Honor form choices and list filters must allow historical rows to remain visible to authorized laboran after the old aslab becomes inactive. Do not filter laboran financial history solely by `asleb__status='aktif'`.

- [ ] **Step 5: Generate migration and run honor plus PDF regressions**

Run:

```powershell
python manage.py makemigrations asleb --name honor_reassignment_audit
python manage.py test apps.pendaftaran_asleb.test_replacement_services.HonorReassignmentTests apps.asleb --keepdb -v 2
```

Expected: PASS; existing honor PDF generation still uses `HonorAsleb` and receives the corrected recipient for unlocked months.

- [ ] **Step 6: Commit honor transfer behavior**

```powershell
git add apps/asleb/models.py apps/asleb/migrations/0027_honor_reassignment_audit.py apps/pendaftaran_asleb/replacement_services.py apps/pendaftaran_asleb/test_replacement_services.py apps/asleb/views.py
git commit -m "feat: reassign replacement honor by month"
```

### Task 8: Activate Verified Replacements and Preserve Operations

**Files:**
- Modify: `apps/pendaftaran_asleb/replacement_services.py`
- Modify: `apps/pendaftaran_asleb/services.py`
- Modify: `apps/pendaftaran_asleb/test_replacement_services.py`
- Modify: `apps/asleb/tests.py`

- [ ] **Step 1: Write failing activation and preservation tests**

```python
def test_activation_promotes_candidate_and_links_same_slot(self):
    assignment = activate_replacement(
        offer_id=self.submitted_offer.pk,
        actor=self.laboran,
        active_date=date(2026, 11, 5),
    )
    self.candidate.refresh_from_db()
    self.slot.refresh_from_db()
    self.assertEqual(assignment.slot, self.outgoing_assignment.slot)
    self.assertEqual(assignment.menggantikan, self.outgoing_assignment)
    self.assertEqual(self.candidate.role, 'asisten_lab')
    self.assertEqual(self.slot.status, AslabSlot.STATUS_ACTIVE)

def test_activation_does_not_move_completed_attendance(self):
    activate_replacement(offer_id=self.submitted_offer.pk, actor=self.laboran, active_date=self.today)
    self.attendance.refresh_from_db()
    self.assertEqual(self.attendance.asleb, self.outgoing_asleb)
```

- [ ] **Step 2: Run activation tests and verify failure**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_services.ActivationServiceTests -v 2
```

Expected: FAIL because activation is incomplete.

- [ ] **Step 3: Implement activation as one transaction**

`activate_replacement` must lock the offer, replacement, slot, and assignments; require `offer.status='submitted'`; revalidate the candidate; create or update the existing `Asleb` person record; create the incoming active assignment linked with `menggantikan`; run honor reassignment; activate the slot; update replacement and offer statuses; promote the user; and write audit entries.

Use the existing registration-to-aslab field mapping, extracted into a shared helper so regular acceptance and replacement activation do not diverge:

```python
def sync_asleb_person_from_registration(registration, *, period, status='aktif'):
    return Asleb.objects.update_or_create(
        nim=registration.nim,
        defaults={
            'nama': registration.nama,
            'no_hp': registration.no_hp,
            'email': registration.email,
            'program_studi': registration.program_studi,
            'matkul': str(registration.matkul),
            'semester': registration.semester,
            'periode_aktif': period,
            'tanggal_bergabung': timezone.localdate(),
            'status': status,
        },
    )[0]
```

Do not update `AbsensiAsleb`, `AbsensiMasukAsleb`, `HasilPraktikumMahasiswa`, or completed report actor fields.

- [ ] **Step 4: Adapt period completion to assignment-aware experience**

When a period ends, create experience only for assignments with `status='active'` that transition to `completed`. Use each assignment's actual `mulai_pada`, mark replacement context in the description, and never create experience for `resigned`, `terminated`, or `replaced` assignments. Preserve the current role-demotion semantics.

- [ ] **Step 5: Run activation, period, attendance, and grading regressions**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_services apps.asleb apps.jadwal --keepdb -v 2
```

Expected: PASS. Existing completed attendance and grading rows remain present and associated with their original records.

- [ ] **Step 6: Commit activation behavior**

```powershell
git add apps/pendaftaran_asleb/replacement_services.py apps/pendaftaran_asleb/services.py apps/pendaftaran_asleb/test_replacement_services.py apps/asleb/tests.py
git commit -m "feat: activate verified aslab replacements"
```

### Task 9: Implement Limited Replacement Registration

**Files:**
- Modify: `apps/pendaftaran_asleb/replacement_forms.py`
- Modify: `apps/pendaftaran_asleb/replacement_services.py`
- Modify: `apps/pendaftaran_asleb/test_replacement_services.py`

- [ ] **Step 1: Write failing targeted-opening tests**

```python
def test_limited_opening_does_not_open_regular_registration(self):
    opening = open_limited_registration(
        replacement_id=self.replacement.pk,
        actor=self.laboran,
        opens_at=timezone.now(),
        closes_at=timezone.now() + timedelta(days=5),
    )
    self.assertTrue(opening.is_open)
    self.assertFalse(is_registration_open())

def test_selecting_candidate_closes_other_live_applications(self):
    offer = select_limited_candidate(
        opening_id=self.opening.pk,
        registration_id=self.selected.pk,
        actor=self.laboran,
    )
    self.other.refresh_from_db()
    self.assertEqual(offer.status, AslabOffer.STATUS_WAITING)
    self.assertEqual(self.other.status, PendaftaranAsleb.STATUS_TIDAK_TERPILIH)
```

- [ ] **Step 2: Run tests and verify service failures**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_services.LimitedRegistrationTests -v 2
```

Expected: FAIL before limited-opening services exist.

- [ ] **Step 3: Implement opening, eligibility, application, and selection services**

Public interfaces:

```python
open_limited_registration(*, replacement_id, actor, opens_at, closes_at, program_studi='', cohort=None, allowed_candidate_ids=(), requirements='')
submit_limited_application(*, opening_id, candidate, cleaned_data, files)
select_limited_candidate(*, opening_id, registration_id, actor) -> AslabOffer
close_limited_registration(*, opening_id, actor)
```

The opening quota is fixed at one. Course and period always come from the slot. Eligibility enforces the optional study-program, cohort, and candidate-allowlist filters. Selecting a candidate creates a consent offer rather than activating immediately; the candidate must still accept and submit complete data. The global `PengaturanPendaftaranAsleb` singleton is never modified.

- [ ] **Step 4: Run limited and regular registration suites**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_services.LimitedRegistrationTests apps.pendaftaran_asleb.tests.PendaftaranAslebViewTests --keepdb -v 2
```

Expected: PASS.

- [ ] **Step 5: Commit limited registration logic**

```powershell
git add apps/pendaftaran_asleb/replacement_forms.py apps/pendaftaran_asleb/replacement_services.py apps/pendaftaran_asleb/test_replacement_services.py
git commit -m "feat: add limited aslab replacement registration"
```

### Task 10: Add Notifications Without Coupling Transactions

**Files:**
- Create: `apps/pendaftaran_asleb/replacement_notifications.py`
- Modify: `apps/pendaftaran_asleb/replacement_services.py`
- Modify: `apps/pendaftaran_asleb/test_replacement_services.py`

- [ ] **Step 1: Write failing notification scheduling tests**

```python
@mock.patch('apps.pendaftaran_asleb.replacement_services.transaction.on_commit')
def test_offer_notification_is_scheduled_after_commit(self, on_commit):
    create_direct_offer(
        replacement_id=self.replacement.pk,
        candidate_id=self.candidate.pk,
        deadline=self.deadline,
        actor=self.laboran,
    )
    on_commit.assert_called_once()

@mock.patch('apps.pendaftaran_asleb.replacement_notifications.send_branded_email', side_effect=RuntimeError)
def test_email_failure_does_not_reverse_activation(self, _send):
    activate_replacement(offer_id=self.submitted_offer.pk, actor=self.laboran, active_date=self.today)
    self.assertEqual(AslabReplacement.objects.get(pk=self.replacement.pk).status, 'active')
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_services.ReplacementNotificationTests -v 2
```

Expected: FAIL before notification callbacks exist.

- [ ] **Step 3: Implement event-specific notification wrappers**

Provide functions:

```python
notify_assignment_ended(replacement_id)
notify_offer_sent(offer_id)
notify_offer_response(offer_id)
notify_submission_ready(offer_id)
notify_submission_returned(offer_id)
notify_replacement_activated(replacement_id)
notify_honor_correction_required(replacement_id)
```

Each function reloads its objects by ID, sends the existing realtime notification, attempts branded email with `fail_silently=True`, and never receives sensitive bank details in its payload. Services call them only through `transaction.on_commit(lambda: ...)`.

- [ ] **Step 4: Run notification tests**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_services.ReplacementNotificationTests -v 2
```

Expected: PASS.

- [ ] **Step 5: Commit notifications**

```powershell
git add apps/pendaftaran_asleb/replacement_notifications.py apps/pendaftaran_asleb/replacement_services.py apps/pendaftaran_asleb/test_replacement_services.py
git commit -m "feat: notify aslab replacement events"
```

### Task 11: Add Laboran and Student Web Workflows

**Files:**
- Create: `apps/pendaftaran_asleb/replacement_views.py`
- Modify: `apps/pendaftaran_asleb/urls.py`
- Create: `apps/pendaftaran_asleb/templates/pendaftaran_asleb/replacement_list.html`
- Create: `apps/pendaftaran_asleb/templates/pendaftaran_asleb/replacement_detail.html`
- Create: `apps/pendaftaran_asleb/templates/pendaftaran_asleb/replacement_end_form.html`
- Create: `apps/pendaftaran_asleb/templates/pendaftaran_asleb/replacement_offer_form.html`
- Create: `apps/pendaftaran_asleb/templates/pendaftaran_asleb/replacement_opening_form.html`
- Create: `apps/pendaftaran_asleb/templates/pendaftaran_asleb/replacement_candidate_form.html`
- Create: `apps/pendaftaran_asleb/templates/pendaftaran_asleb/replacement_verify.html`
- Create: `apps/pendaftaran_asleb/test_replacement_views.py`
- Modify: `apps/asleb/templates/asleb/asleb_list.html`

- [ ] **Step 1: Write failing authorization and workflow view tests**

```python
def test_student_cannot_open_laboran_replacement_dashboard(self):
    self.login_as(self.student)
    response = self.client.get(reverse('pendaftaran_asleb:replacement_list'))
    self.assertEqual(response.status_code, 302)

def test_candidate_can_only_respond_to_own_offer(self):
    self.login_as(self.other_student)
    response = self.client.post(reverse('pendaftaran_asleb:replacement_offer_accept', args=[self.offer.pk]))
    self.assertEqual(response.status_code, 404)

def test_end_form_previews_monthly_honor_boundary(self):
    self.login_as(self.laboran)
    response = self.client.get(reverse('pendaftaran_asleb:replacement_end', args=[self.assignment.pk]))
    self.assertContains(response, 'Honor sebelum bulan efektif tetap menjadi hak aslab lama')
```

- [ ] **Step 2: Run view tests and verify missing-route failures**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_views -v 2
```

Expected: FAIL with `NoReverseMatch`.

- [ ] **Step 3: Add explicit routes and thin views**

Routes:

```python
path('pergantian/', ReplacementListView.as_view(), name='replacement_list'),
path('pergantian/<int:pk>/', ReplacementDetailView.as_view(), name='replacement_detail'),
path('pergantian/akhiri/<int:assignment_id>/', EndAssignmentView.as_view(), name='replacement_end'),
path('pergantian/<int:pk>/tawaran/', CreateOfferView.as_view(), name='replacement_offer_create'),
path('tawaran/<int:pk>/terima/', AcceptOfferView.as_view(), name='replacement_offer_accept'),
path('tawaran/<int:pk>/tolak/', DeclineOfferView.as_view(), name='replacement_offer_decline'),
path('tawaran/<int:pk>/data/', CandidateSubmissionView.as_view(), name='replacement_candidate_data'),
path('tawaran/<int:pk>/verifikasi/', VerifyOfferView.as_view(), name='replacement_verify'),
path('pergantian/<int:pk>/pendaftaran-terbatas/', LimitedOpeningView.as_view(), name='replacement_opening'),
```

Views validate permissions, bind forms, invoke services, display messages, and redirect. They must not update workflow models directly.

- [ ] **Step 4: Build feature-complete templates using existing components**

The laboran list displays course, slot, outgoing aslab, current candidate, state, deadline, held months, and correction warnings. The student offer page displays course, period, remaining responsibility, transfer month, deadline, and accept/decline controls. Use existing Lucide icons and confirmation modal patterns; do not use browser `prompt()`.

- [ ] **Step 5: Replace the old list action with the new workflow entry**

For active assignments, render **Ganti/Akhiri Masa Tugas** linking to `replacement_end`. For legacy active rows without an assignment, render an informational warning and no destructive action. Keep the old POST route only for backward compatibility with stale links.

- [ ] **Step 6: Run view and existing list tests**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb.test_replacement_views apps.asleb.tests.AslebViewTests --keepdb -v 2
```

Expected: PASS.

- [ ] **Step 7: Commit web workflows**

```powershell
git add apps/pendaftaran_asleb/replacement_views.py apps/pendaftaran_asleb/urls.py apps/pendaftaran_asleb/templates/pendaftaran_asleb apps/pendaftaran_asleb/test_replacement_views.py apps/asleb/templates/asleb/asleb_list.html
git commit -m "feat: add aslab replacement screens"
```

### Task 12: Guard Deletion and Verify End to End

**Files:**
- Modify: `apps/asleb/views.py`
- Modify: `apps/asleb/templates/asleb/asleb_detail.html`
- Modify: `apps/asleb/tests.py`
- Modify: `docs/superpowers/specs/2026-07-21-aslab-replacement-workflow-design.md` only if implementation reveals an approved factual correction

- [ ] **Step 1: Add failing delete-protection tests**

```python
def test_aslab_with_operational_history_cannot_be_deleted(self):
    AslabAssignment.objects.create(
        slot=self.slot, asleb=self.asleb,
        mulai_pada=self.period.mulai,
        status=AslabAssignment.STATUS_TERMINATED,
    )
    response = self.client.post(reverse('asleb:asleb_delete', args=[self.asleb.pk]))
    self.assertRedirects(response, reverse('asleb:asleb_detail', args=[self.asleb.pk]))
    self.assertTrue(Asleb.objects.filter(pk=self.asleb.pk).exists())
```

- [ ] **Step 2: Run deletion test and verify current destructive behavior fails it**

Run:

```powershell
python manage.py test apps.asleb.tests.AslebViewTests.test_aslab_with_operational_history_cannot_be_deleted -v 2
```

Expected: FAIL because the current delete view permits deletion or cascades related data.

- [ ] **Step 3: Add protected deletion behavior**

Override `AslebDeleteView.post()` to reject deletion when any assignment, honor, attendance, report, or reminder relation exists. Permit deletion only for unused mistaken records. Show **Ganti/Akhiri Masa Tugas** instead of delete for records with history.

- [ ] **Step 4: Run migration checks**

Run:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py check --deploy
```

Expected: no uncommitted model changes; migration plan contains only the four reviewed feature migrations; deploy checks contain no new feature-caused errors.

- [ ] **Step 5: Run focused and full test suites**

Run:

```powershell
python manage.py test apps.pendaftaran_asleb apps.asleb apps.jadwal apps.pengguna --keepdb
python manage.py test --keepdb
```

Expected: PASS.

- [ ] **Step 6: Exercise both workflows manually**

Run:

```powershell
python manage.py runserver 127.0.0.1:8000
```

Verify in the browser:

1. Laboran ends an assignment effective mid-month.
2. Old aslab loses access and has no generated experience.
3. Direct candidate receives an offer, accepts, completes data, and remains mahasiswa until verification.
4. Laboran verifies and activates; the same slot becomes active and current-month honor changes recipient.
5. A paid honor creates a correction warning instead of changing silently.
6. Limited registration remains separate from regular registration and closes after one candidate is selected.
7. Completed attendance, grades, reports, and old honor months still display under the old aslab.

- [ ] **Step 7: Review the final diff for compatibility and secrets**

Run:

```powershell
git diff main...HEAD --check
git diff main...HEAD --stat
git grep -n -E "(SECRET_KEY=|DB_PASSWORD=|LABHUB_LICENSE_KEY=)" -- . ":(exclude).env*"
```

Expected: no whitespace errors, no unrelated files, and no newly committed secret values.

- [ ] **Step 8: Commit final guards**

```powershell
git add apps/asleb/views.py apps/asleb/templates/asleb/asleb_detail.html apps/asleb/tests.py
git commit -m "fix: protect historical aslab records"
```

## Release Sequence

1. Back up the MySQL database.
2. Run `python manage.py audit_aslab_slots --strict` against a restored staging copy.
3. Resolve every ambiguous active legacy aslab before production migration.
4. Deploy migrations and code together; nullable registration fields keep old flows compatible.
5. Smoke-test regular registration before testing replacement.
6. Test one replacement using non-production/sample users.
7. Verify honor for the prior month, effective month, and a locked month.
8. Keep the previous container image available for rollback. Database rollback is by backup restoration because assignment/audit records are intentionally durable.

## Completion Gate

Implementation is complete only when:

- all acceptance criteria in the design document map to passing tests;
- regular registration, period closing, attendance, grading, reports, honor PDF, and role-based navigation pass regression tests;
- no historical operational row is deleted or reassigned during early termination;
- migrations have been tested on a recent database copy;
- direct offers and limited registration both require candidate consent and laboran verification;
- whole-month honor behavior is demonstrated for delayed activation and locked payment records.
