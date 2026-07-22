import base64
from datetime import date, datetime
from queue import Queue
from threading import Barrier, Event, Thread
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, close_old_connections, connection, transaction
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.asleb.models import Asleb, HonorAsleb, HonorReassignment, SuratHonorAsleb
from apps.asleb.views import HonorAslebListView
from apps.pengguna.models import PengalamanPengguna, Pengguna

from .models import (
    AslabAssignment,
    AslabOffer,
    AslabReplacement,
    AslabReplacementAudit,
    AslabSlot,
    MataKuliahAsleb,
    PeriodeAsleb,
    PendaftaranAsleb,
)
from .replacement_forms import DirectOfferForm, ReplacementCandidateForm
from .replacement_services import (
    accept_offer,
    activate_replacement,
    create_direct_offer,
    decline_offer,
    end_assignment_for_replacement,
    end_single_active_assignment_for_replacement,
    expire_due_offers,
    hold_replacement_honor,
    payment_eligible_honors,
    reconcile_retrospective_honor,
    reassign_replacement_honor,
    return_offer_for_revision,
    submit_offer_registration,
)
from .services import sync_expired_asleb_periods


class HonorReassignmentTests(TestCase):
    def setUp(self):
        self.period = PeriodeAsleb.objects.create(
            tahun=2026, semester=2, mulai=date(2026, 7, 1), selesai=date(2026, 12, 31),
            pendaftaran_mulai=date(2026, 7, 1), pendaftaran_selesai=date(2026, 7, 30),
        )
        self.course = MataKuliahAsleb.objects.create(
            kode='HON01', kode_mk='HON01', nama='Honor Replacement', dosen='Dosen', kelas='TIF-01',
        )
        self.slot = AslabSlot.objects.create(
            periode=self.period, matkul=self.course, nomor=1, status=AslabSlot.STATUS_VACANT,
        )
        self.laboran = self.user('LAB-HON', 'Laboran Honor', 'laboran')
        self.outgoing = self.asleb('OLD-HON', 'Aslab Lama', 'nonaktif')
        self.incoming = self.asleb('NEW-HON', 'Aslab Baru', 'aktif')
        assignment = AslabAssignment.objects.create(
            slot=self.slot, asleb=self.outgoing, mulai_pada=date(2026, 7, 1),
            berakhir_pada=date(2026, 10, 5), status=AslabAssignment.STATUS_RESIGNED,
        )
        self.replacement = AslabReplacement.objects.create(
            slot=self.slot, outgoing_assignment=assignment, effective_date=date(2026, 10, 5),
            transfer_month=date(2026, 10, 1), created_by=self.laboran,
        )

    def user(self, nim, name, role):
        return Pengguna.objects.create(
            nama_pengguna=name, nim_nik=nim, email=f'{nim.lower()}@example.com', password='secret',
            no_hp='08123', alamat='Jakarta', fakultas='FTI', prodi='TI', gender='laki_laki',
            role=role, is_verified=True,
        )

    def asleb(self, nim, name, status):
        return Asleb.objects.create(
            nama=name, nim=nim, no_hp='08123', email=f'{nim.lower()}@example.com',
            program_studi='TI', semester=5, status=status, periode_aktif=self.period,
            tanggal_bergabung=date(2026, 7, 1),
        )

    def honor(self, asleb, month, status='draft'):
        return HonorAsleb.objects.create(
            asleb=asleb, bulan=month, total_pertemuan=2, jumlah=98000, status=status,
            assigned_laboran=self.laboran,
        )

    def run_service(self):
        return reassign_replacement_honor(
            replacement=self.replacement, incoming_asleb=self.incoming, actor=self.laboran,
        )

    def replacement_registration(self, **overrides):
        candidate = self.user('USR-NEW-HON', 'Aslab Baru', 'mahasiswa')
        values = {
            'nama': self.incoming.nama,
            'nim': self.incoming.nim,
            'no_hp': self.incoming.no_hp,
            'email': self.incoming.email,
            'program_studi': self.incoming.program_studi,
            'semester': self.incoming.semester,
            'matkul': self.course,
            'periode': self.period,
            'metode_rekening': 'bank_lain',
            'rekening': '99887766',
            'nama_pemilik_rekening': 'Aslab Baru',
            'status': 'diterima',
            'jenis': PendaftaranAsleb.JENIS_REPLACEMENT,
            'replacement_process': self.replacement,
            'candidate_user': candidate,
        }
        values.update(overrides)
        return PendaftaranAsleb.objects.create(**values)

    def test_prior_month_untouched_and_effective_through_period_end_reassigned(self):
        self.replacement_registration()
        prior = self.honor(self.outgoing, date(2026, 9, 1))
        effective = self.honor(self.outgoing, date(2026, 10, 1))
        future = self.honor(self.outgoing, date(2026, 12, 1))

        self.run_service()

        prior.refresh_from_db(); effective.refresh_from_db(); future.refresh_from_db()
        self.assertEqual(prior.asleb, self.outgoing)
        self.assertEqual(effective.asleb, self.incoming)
        self.assertEqual(future.asleb, self.incoming)
        self.assertFalse(HonorReassignment.objects.filter(honor=prior).exists())
        self.assertEqual(
            set(HonorReassignment.objects.values_list('status', flat=True)),
            {HonorReassignment.STATUS_REASSIGNED},
        )

    def test_paid_honor_is_not_rewritten_and_requires_correction(self):
        paid = self.honor(self.outgoing, date(2026, 10, 1), status='dibayar')

        self.run_service()

        paid.refresh_from_db()
        audit = HonorReassignment.objects.get(honor=paid)
        self.assertEqual(paid.asleb, self.outgoing)
        self.assertEqual(audit.status, HonorReassignment.STATUS_CORRECTION_REQUIRED)
        self.assertEqual(audit.final_asleb, self.incoming)

    def test_idempotent_and_does_not_fabricate_missing_months(self):
        self.replacement_registration()
        existing = self.honor(self.outgoing, date(2026, 11, 1))

        first = self.run_service()
        second = self.run_service()

        self.assertEqual(first, second)
        self.assertEqual(HonorAsleb.objects.count(), 1)
        self.assertEqual(HonorReassignment.objects.count(), 1)
        audit = HonorReassignment.objects.get(honor=existing)
        self.assertEqual(audit.original_asleb, self.outgoing)
        self.assertEqual(audit.final_asleb, self.incoming)

    def test_honor_after_period_end_is_untouched(self):
        outside = self.honor(self.outgoing, date(2027, 1, 1))

        self.run_service()

        outside.refresh_from_db()
        self.assertEqual(outside.asleb, self.outgoing)
        self.assertFalse(HonorReassignment.objects.exists())

    def test_laboran_honor_history_keeps_inactive_outgoing_aslab_visible(self):
        historical = self.honor(self.outgoing, date(2026, 9, 1))
        request = RequestFactory().get('/asleb/honor/')
        request.current_pengguna = self.laboran
        view = HonorAslebListView()
        view.request = request

        self.assertIn(historical, view.get_queryset())

    def test_hold_is_idempotent_visible_and_excluded_from_payment_selection(self):
        honor = self.honor(self.outgoing, date(2026, 10, 1))

        self.assertEqual(hold_replacement_honor(replacement=self.replacement, actor=self.laboran), 1)
        self.assertEqual(hold_replacement_honor(replacement=self.replacement, actor=self.laboran), 0)

        audit = HonorReassignment.objects.get(honor=honor)
        self.assertEqual(audit.status, HonorReassignment.STATUS_HELD)
        self.assertIn(honor, HonorAsleb.objects.all())
        self.assertNotIn(honor, payment_eligible_honors(HonorAsleb.objects.all()))

    def test_honor_created_after_termination_is_held_by_workflow_then_reassigned(self):
        late_honor = self.honor(self.outgoing, date(2026, 11, 1))
        self.assertFalse(HonorReassignment.objects.filter(honor=late_honor).exists())

        self.assertNotIn(late_honor, payment_eligible_honors(HonorAsleb.objects.all()))
        request = RequestFactory().get('/asleb/honor/')
        request.current_pengguna = self.laboran
        view = HonorAslebListView()
        view.request = request
        self.assertIn(late_honor, view.get_queryset())

        self.replacement_registration()
        self.run_service()

        late_honor.refresh_from_db()
        self.assertEqual(late_honor.asleb, self.incoming)
        self.assertIn(late_honor, payment_eligible_honors(HonorAsleb.objects.all()))
        self.assertEqual(
            HonorReassignment.objects.get(honor=late_honor).status,
            HonorReassignment.STATUS_REASSIGNED,
        )

    def test_cancelled_replacement_explicitly_releases_late_honor(self):
        late_honor = self.honor(self.outgoing, date(2026, 11, 1))
        self.replacement.status = AslabReplacement.STATUS_CANCELLED
        self.replacement.save(update_fields=['status', 'updated_at'])

        self.assertIn(late_honor, payment_eligible_honors(HonorAsleb.objects.all()))

    def test_retrospective_honor_after_active_reconciles_to_incoming_account(self):
        self.replacement_registration()
        incoming_assignment = AslabAssignment.objects.create(
            slot=self.slot,
            asleb=self.incoming,
            mulai_pada=date(2026, 10, 5),
            status=AslabAssignment.STATUS_ACTIVE,
            menggantikan=self.replacement.outgoing_assignment,
        )
        self.replacement.incoming_assignment = incoming_assignment
        self.replacement.status = AslabReplacement.STATUS_ACTIVE
        self.replacement.activated_by = self.laboran
        self.replacement.save(update_fields=[
            'incoming_assignment', 'status', 'activated_by', 'updated_at',
        ])
        late_honor = self.honor(self.outgoing, date(2026, 11, 1))

        self.assertNotIn(late_honor, payment_eligible_honors(HonorAsleb.objects.all()))
        reconciled = reconcile_retrospective_honor(honor=late_honor, actor=self.laboran)

        late_honor.refresh_from_db()
        self.assertEqual(reconciled.pk, late_honor.pk)
        self.assertEqual(late_honor.asleb, self.incoming)
        self.assertEqual(late_honor.metode_transfer, 'bank_lain')
        self.assertEqual(late_honor.nomor_transfer, '99887766')
        self.assertEqual(late_honor.nama_pemilik_transfer, 'Aslab Baru')
        self.assertEqual(
            HonorReassignment.objects.get(honor=late_honor).status,
            HonorReassignment.STATUS_REASSIGNED,
        )
        self.assertIn(late_honor, payment_eligible_honors(HonorAsleb.objects.all()))

    def test_manual_honor_creation_boundary_reconciles_active_replacement(self):
        self.replacement_registration()
        incoming_assignment = AslabAssignment.objects.create(
            slot=self.slot,
            asleb=self.incoming,
            mulai_pada=date(2026, 10, 5),
            status=AslabAssignment.STATUS_ACTIVE,
            menggantikan=self.replacement.outgoing_assignment,
        )
        self.replacement.incoming_assignment = incoming_assignment
        self.replacement.status = AslabReplacement.STATUS_ACTIVE
        self.replacement.activated_by = self.laboran
        self.replacement.save(update_fields=[
            'incoming_assignment', 'status', 'activated_by', 'updated_at',
        ])
        session = self.client.session
        session['pengguna_id'] = self.laboran.pk
        session.save()

        response = self.client.post(reverse('asleb:honor_create'), {
            'asleb': self.outgoing.pk,
            'bulan': '2026-11-01',
            'jumlah_praktikum': 1,
            'total_pertemuan': 2,
            'metode_transfer': 'bni',
            'nomor_transfer': 'OLD-ACCOUNT',
            'nama_pemilik_transfer': 'Aslab Lama',
            'tanggal_transfer': '',
            'pic_transfer': '',
            'status': 'diproses',
            'keterangan': '',
        })

        self.assertRedirects(response, reverse('asleb:honor_list'))
        honor = HonorAsleb.objects.get(bulan=date(2026, 11, 1))
        self.assertEqual(honor.asleb, self.incoming)
        self.assertEqual(honor.nomor_transfer, '99887766')
        self.assertEqual(honor.nama_pemilik_transfer, 'Aslab Baru')
        self.assertEqual(
            HonorReassignment.objects.get(honor=honor).status,
            HonorReassignment.STATUS_REASSIGNED,
        )
        self.assertIn(honor, payment_eligible_honors(HonorAsleb.objects.all()))

    def test_held_audit_requires_real_honor_row(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                HonorReassignment.objects.create(
                    replacement=self.replacement,
                    honor=None,
                    bulan=date(2026, 10, 1),
                    original_asleb=self.outgoing,
                    status=HonorReassignment.STATUS_HELD,
                    reason='Invalid null hold',
                    acted_by=self.laboran,
                )

    def test_issued_document_is_locked_and_requires_correction(self):
        honor = self.honor(self.outgoing, date(2026, 10, 1))
        surat = SuratHonorAsleb.objects.create(
            bulan=date(2026, 10, 1), nomor_surat='001/HON/X/2026',
            file_pdf='surat_honor_asleb/issued.pdf', dibuat_oleh=self.laboran,
        )
        surat.honors.add(honor)

        self.run_service()

        honor.refresh_from_db()
        audit = HonorReassignment.objects.get(honor=honor)
        self.assertEqual(honor.asleb, self.outgoing)
        self.assertEqual(audit.status, HonorReassignment.STATUS_CORRECTION_REQUIRED)
        self.assertEqual(audit.final_asleb, self.incoming)
        self.assertNotIn(honor, payment_eligible_honors(HonorAsleb.objects.all()))

    def test_unlocked_reassignment_uses_incoming_registration_account(self):
        self.replacement_registration()
        honor = self.honor(self.outgoing, date(2026, 10, 1))
        honor.metode_transfer = 'bni'
        honor.nomor_transfer = 'OLD-ACCOUNT'
        honor.nama_pemilik_transfer = 'Aslab Lama'
        HonorAsleb.objects.filter(pk=honor.pk).update(
            metode_transfer=honor.metode_transfer,
            nomor_transfer=honor.nomor_transfer,
            nama_pemilik_transfer=honor.nama_pemilik_transfer,
        )

        self.run_service()

        honor.refresh_from_db()
        self.assertEqual(honor.asleb, self.incoming)
        self.assertEqual(honor.metode_transfer, 'bank_lain')
        self.assertEqual(honor.nomor_transfer, '99887766')
        self.assertEqual(honor.nama_pemilik_transfer, 'Aslab Baru')

    def test_missing_incoming_account_rolls_back_without_mutation(self):
        self.replacement_registration(rekening='', nama_pemilik_rekening='')
        honor = self.honor(self.outgoing, date(2026, 10, 1))

        with self.assertRaisesMessage(ValidationError, 'rekening'):
            self.run_service()

        honor.refresh_from_db()
        self.assertEqual(honor.asleb, self.outgoing)
        self.assertFalse(HonorReassignment.objects.exists())


class DirectOfferServiceTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.period = PeriodeAsleb.objects.create(
            tahun=2026, semester=2, mulai=date(2026, 7, 1), selesai=date(2026, 12, 31),
            pendaftaran_mulai=date(2026, 7, 1), pendaftaran_selesai=date(2026, 7, 30),
        )
        self.course = MataKuliahAsleb.objects.create(
            kode='OFF_TIF01', kode_mk='OFF01', nama='Offer Test', dosen='Dosen', kelas='TIF-01',
        )
        self.slot = AslabSlot.objects.create(
            periode=self.period, matkul=self.course, nomor=1, status=AslabSlot.STATUS_VACANT,
        )
        self.laboran = self.user('LAB-OFF', 'Laboran', 'laboran')
        self.candidate = self.user('STU-OFF', 'Candidate', 'mahasiswa')
        outgoing_user = self.user('OLD-OFF', 'Old Aslab', 'mahasiswa')
        outgoing = Asleb.objects.create(
            nama='Old Aslab', nim=outgoing_user.nim_nik, no_hp='081', email=outgoing_user.email,
            program_studi='TI', semester=5, status='nonaktif', periode_aktif=self.period,
            tanggal_bergabung=date(2026, 7, 1),
        )
        assignment = AslabAssignment.objects.create(
            slot=self.slot, asleb=outgoing, mulai_pada=date(2026, 7, 1),
            berakhir_pada=date(2026, 9, 1), status=AslabAssignment.STATUS_RESIGNED,
        )
        self.replacement = AslabReplacement.objects.create(
            slot=self.slot, outgoing_assignment=assignment, effective_date=date(2026, 9, 1),
            transfer_month=date(2026, 9, 1), created_by=self.laboran,
        )

    def user(self, nim, name, role, verified=True):
        return Pengguna.objects.create(
            nama_pengguna=name, nim_nik=nim, email=f'{nim.lower()}@example.com', password='secret',
            no_hp='08123', alamat='Jakarta', fakultas='FTI', prodi='TI', gender='laki_laki',
            role=role, is_verified=verified,
        )

    def create_offer(self, **overrides):
        values = dict(replacement_id=self.replacement.pk, candidate_id=self.candidate.pk,
                      deadline=self.now + timezone.timedelta(days=3), actor=self.laboran)
        values.update(overrides)
        return create_direct_offer(**values)

    def test_create_accept_decline_and_expire_transitions(self):
        offer = self.create_offer()
        self.replacement.refresh_from_db()
        self.assertEqual((offer.status, self.replacement.method, self.replacement.status), (
            AslabOffer.STATUS_WAITING, AslabReplacement.METHOD_DIRECT_OFFER,
            AslabReplacement.STATUS_WAITING_CONSENT,
        ))
        accepted = accept_offer(offer_id=offer.pk, candidate=self.candidate)
        self.candidate.refresh_from_db(); self.replacement.refresh_from_db()
        self.assertEqual(accepted.status, AslabOffer.STATUS_ACCEPTED_INCOMPLETE)
        self.assertEqual(self.replacement.status, AslabReplacement.STATUS_COMPLETING_DATA)
        self.assertEqual(self.candidate.role, 'mahasiswa')

        accepted.status = AslabOffer.STATUS_DECLINED
        accepted.save(update_fields=['status'])
        self.replacement.status = AslabReplacement.STATUS_WAITING_ACTION
        self.replacement.save(update_fields=['status'])
        second = self.create_offer()
        declined = decline_offer(offer_id=second.pk, candidate=self.candidate, reason='Tidak bersedia')
        self.replacement.refresh_from_db()
        self.assertEqual(declined.decline_reason, 'Tidak bersedia')
        self.assertEqual(self.replacement.status, AslabReplacement.STATUS_WAITING_ACTION)

        third = self.create_offer(deadline=self.now + timezone.timedelta(days=1))
        self.assertEqual(expire_due_offers(now=third.deadline), 1)
        self.assertEqual(expire_due_offers(now=third.deadline), 0)
        third.refresh_from_db()
        self.assertEqual(third.status, AslabOffer.STATUS_EXPIRED)

    def test_period_completion_experience_uses_assignment_start_and_skips_outgoing(self):
        offer = self.submitted_offer()
        incoming = activate_replacement(
            offer_id=offer.pk, actor=self.laboran, active_date=date(2026, 9, 5),
        )

        sync_expired_asleb_periods(date(2027, 1, 1))

        incoming.refresh_from_db()
        self.replacement.outgoing_assignment.refresh_from_db()
        experience = PengalamanPengguna.objects.get(pengguna=self.candidate, otomatis=True)
        self.assertEqual(incoming.status, AslabAssignment.STATUS_COMPLETED)
        self.assertEqual(experience.tanggal_mulai, date(2026, 9, 5))
        self.assertIn('pengganti', experience.deskripsi.lower())
        self.assertFalse(PengalamanPengguna.objects.filter(
            pengguna__nim_nik=self.replacement.outgoing_assignment.asleb.nim,
            otomatis=True,
        ).exists())

    def test_period_completion_never_awards_resigned_or_replaced_assignments(self):
        outgoing_user = Pengguna.objects.get(nim_nik=self.replacement.outgoing_assignment.asleb.nim)
        self.replacement.outgoing_assignment.status = AslabAssignment.STATUS_REPLACED
        self.replacement.outgoing_assignment.save(update_fields=['status'])

        sync_expired_asleb_periods(date(2027, 1, 1))

        self.assertFalse(PengalamanPengguna.objects.filter(
            pengguna=outgoing_user, otomatis=True,
        ).exists())

    def test_rejects_unauthorized_ineligible_conflicting_and_invalid_deadline(self):
        invalid = self.user('BAD-OFF', 'Bad', 'admin')
        for overrides, message in [
            ({'actor': self.candidate}, 'laboran'),
            ({'candidate_id': invalid.pk}, 'mahasiswa'),
            ({'deadline': self.now}, 'masa depan'),
        ]:
            with self.subTest(overrides=overrides):
                with self.assertRaisesMessage(ValidationError, message): self.create_offer(**overrides)
        self.create_offer()
        with self.assertRaisesMessage(ValidationError, 'Status'):
            self.create_offer()

    def test_create_offer_only_allows_waiting_action_or_searching_parent(self):
        rejected_states = [
            AslabReplacement.STATUS_WAITING_CONSENT,
            AslabReplacement.STATUS_COMPLETING_DATA,
            AslabReplacement.STATUS_WAITING_VERIFICATION,
            AslabReplacement.STATUS_ACTIVE,
            AslabReplacement.STATUS_CANCELLED,
        ]
        for status in rejected_states:
            with self.subTest(status=status):
                self.replacement.status = status
                self.replacement.save(update_fields=['status'])
                with self.assertRaisesMessage(ValidationError, 'Status'):
                    self.create_offer()
                self.assertFalse(AslabOffer.objects.filter(replacement=self.replacement).exists())

        for status in (AslabReplacement.STATUS_WAITING_ACTION, AslabReplacement.STATUS_SEARCHING):
            with self.subTest(status=status):
                self.replacement.status = status
                self.replacement.save(update_fields=['status'])
                offer = self.create_offer()
                self.assertEqual(offer.status, AslabOffer.STATUS_WAITING)
                offer.status = AslabOffer.STATUS_CANCELLED
                offer.save(update_fields=['status'])

    def test_create_offer_does_not_lock_offer_history_rows(self):
        historical = AslabOffer.objects.create(
            replacement=self.replacement, candidate=self.candidate,
            deadline=self.now + timezone.timedelta(days=1),
            status=AslabOffer.STATUS_DECLINED)
        self.assertIsNone(historical.live_replacement_id)
        with CaptureQueriesContext(connection) as queries:
            self.create_offer()
        offer_table = AslabOffer._meta.db_table.lower()
        history_locks = [
            query['sql'] for query in queries.captured_queries
            if offer_table in query['sql'].lower()
            and 'for update' in query['sql'].lower()
        ]
        self.assertEqual(history_locks, [])

    def test_offer_ownership_and_deadline_are_enforced(self):
        offer = self.create_offer(deadline=self.now + timezone.timedelta(days=1))
        other = self.user('OTH-OFF', 'Other', 'mahasiswa')
        with self.assertRaisesMessage(ValidationError, 'kandidat'):
            accept_offer(offer_id=offer.pk, candidate=other)
        with patch('apps.pendaftaran_asleb.replacement_services.timezone.now', return_value=offer.deadline):
            with self.assertRaisesMessage(ValidationError, 'kedaluwarsa'):
                accept_offer(offer_id=offer.pk, candidate=self.candidate)

    def test_accept_decline_and_expire_reject_stale_or_cancelled_parent_and_occupied_slot(self):
        offer = self.create_offer()
        cases = [
            ('accept stale', AslabReplacement.STATUS_WAITING_ACTION, AslabSlot.STATUS_VACANT,
             lambda: accept_offer(offer_id=offer.pk, candidate=self.candidate)),
            ('decline cancelled', AslabReplacement.STATUS_CANCELLED, AslabSlot.STATUS_VACANT,
             lambda: decline_offer(offer_id=offer.pk, candidate=self.candidate)),
        ]
        for label, parent_status, slot_status, operation in cases:
            with self.subTest(label=label):
                self.replacement.status = parent_status
                self.replacement.save(update_fields=['status'])
                self.slot.status = slot_status
                self.slot.save(update_fields=['status'])
                with self.assertRaisesMessage(ValidationError, 'transisi'):
                    operation()
                offer.refresh_from_db()
                self.assertEqual(offer.status, AslabOffer.STATUS_WAITING)

    def test_expiry_batch_skips_stale_offer_without_rolling_back_valid_offer(self):
        valid_offer = self.create_offer(deadline=self.now + timezone.timedelta(days=1))

        other_candidate = self.user('EXP-OTHER', 'Expiry Other', 'mahasiswa')
        other_course = MataKuliahAsleb.objects.create(
            kode='EXP02', kode_mk='EXP02', nama='Expiry Other', dosen='Dosen', kelas='TIF-02')
        other_slot = AslabSlot.objects.create(
            periode=self.period, matkul=other_course, nomor=1, status=AslabSlot.STATUS_VACANT)
        other_asleb = Asleb.objects.create(
            nama='Old Expiry', nim='OLD-EXP', no_hp='081', email='old-exp@example.com',
            program_studi='TI', semester=5, status='nonaktif', periode_aktif=self.period,
            tanggal_bergabung=date(2026, 7, 1))
        other_assignment = AslabAssignment.objects.create(
            slot=other_slot, asleb=other_asleb, mulai_pada=date(2026, 7, 1),
            berakhir_pada=date(2026, 9, 1), status=AslabAssignment.STATUS_RESIGNED)
        stale_replacement = AslabReplacement.objects.create(
            slot=other_slot, outgoing_assignment=other_assignment,
            effective_date=date(2026, 9, 1), transfer_month=date(2026, 9, 1),
            created_by=self.laboran, method=AslabReplacement.METHOD_DIRECT_OFFER,
            status=AslabReplacement.STATUS_CANCELLED)
        stale_offer = AslabOffer.objects.create(
            replacement=stale_replacement, candidate=other_candidate,
            deadline=valid_offer.deadline)

        self.assertEqual(expire_due_offers(now=valid_offer.deadline), 1)
        valid_offer.refresh_from_db()
        stale_offer.refresh_from_db()
        stale_replacement.refresh_from_db()
        self.assertEqual(valid_offer.status, AslabOffer.STATUS_EXPIRED)
        self.assertEqual(stale_offer.status, AslabOffer.STATUS_WAITING)
        self.assertEqual(stale_replacement.status, AslabReplacement.STATUS_CANCELLED)

    def test_submit_and_return_reject_stale_or_cancelled_parent(self):
        offer = accept_offer(offer_id=self.create_offer().pk, candidate=self.candidate)
        form = self.candidate_form(offer)
        self.assertTrue(form.is_valid(), form.errors)
        self.replacement.status = AslabReplacement.STATUS_CANCELLED
        self.replacement.save(update_fields=['status'])
        with self.assertRaisesMessage(ValidationError, 'transisi'):
            submit_offer_registration(
                offer_id=offer.pk, candidate=self.candidate, registration_form=form)
        offer.refresh_from_db()
        self.assertEqual(offer.status, AslabOffer.STATUS_ACCEPTED_INCOMPLETE)

        self.replacement.status = AslabReplacement.STATUS_COMPLETING_DATA
        self.replacement.save(update_fields=['status'])
        registration = submit_offer_registration(
            offer_id=offer.pk, candidate=self.candidate, registration_form=form)
        self.replacement.status = AslabReplacement.STATUS_WAITING_ACTION
        self.replacement.save(update_fields=['status'])
        with self.assertRaisesMessage(ValidationError, 'transisi'):
            return_offer_for_revision(offer_id=offer.pk, actor=self.laboran, notes='Perbaiki')
        offer.refresh_from_db()
        self.assertEqual(offer.status, AslabOffer.STATUS_SUBMITTED)
        self.assertEqual(offer.registration_id, registration.pk)

    def test_candidate_offer_and_registration_conflicts_are_scoped_to_replacement_period(self):
        other_period = PeriodeAsleb.objects.create(
            tahun=2027, semester=1, mulai=date(2027, 1, 1), selesai=date(2027, 6, 30),
            pendaftaran_mulai=date(2027, 1, 1), pendaftaran_selesai=date(2027, 1, 30),
        )
        other_slot = AslabSlot.objects.create(
            periode=other_period, matkul=self.course, nomor=1, status=AslabSlot.STATUS_VACANT)
        other_asleb = Asleb.objects.create(
            nama='Other Old', nim='OLD-OTHER', no_hp='081', email='old-other@example.com',
            program_studi='TI', semester=5, status='nonaktif', periode_aktif=other_period,
            tanggal_bergabung=date(2027, 1, 1))
        other_assignment = AslabAssignment.objects.create(
            slot=other_slot, asleb=other_asleb, mulai_pada=date(2027, 1, 1),
            berakhir_pada=date(2027, 2, 1), status=AslabAssignment.STATUS_RESIGNED)
        other_replacement = AslabReplacement.objects.create(
            slot=other_slot, outgoing_assignment=other_assignment, effective_date=date(2027, 2, 1),
            transfer_month=date(2027, 2, 1), created_by=self.laboran,
            method=AslabReplacement.METHOD_DIRECT_OFFER,
            status=AslabReplacement.STATUS_WAITING_CONSENT)
        AslabOffer.objects.create(
            replacement=other_replacement, candidate=self.candidate,
            deadline=self.now + timezone.timedelta(days=3))

        offer = self.create_offer()
        self.assertEqual(offer.candidate, self.candidate)

        offer.status = AslabOffer.STATUS_DECLINED
        offer.save(update_fields=['status'])
        registration = PendaftaranAsleb.objects.create(
            nama=self.candidate.nama_pengguna, nim=self.candidate.nim_nik, no_hp='081',
            email=self.candidate.email, program_studi='TI', semester=5, matkul=self.course,
            periode=other_period, jenis=PendaftaranAsleb.JENIS_REPLACEMENT,
            replacement_process=other_replacement, candidate_user=self.candidate,
            status='diajukan')
        self.replacement.status = AslabReplacement.STATUS_WAITING_ACTION
        self.replacement.save(update_fields=['status'])
        second = self.create_offer()
        self.assertEqual(second.candidate, registration.candidate_user)

    def candidate_form(self, offer, **changes):
        transcript_content = changes.pop('transcript_content', b'OFF01 Offer Test Nilai A')
        include_files = changes.pop('include_files', True)
        data = {
            'nama': 'Tampered', 'nim': 'TAMPER', 'no_hp': '000', 'email': 'x@example.com',
            'program_studi': 'Wrong', 'semester': 5, 'matkul': self.course.pk,
            'metode_rekening': 'bni', 'rekening': '123456',
            'nama_pemilik_rekening': 'Candidate', 'nilai_transkrip': 'A', 'alasan': 'Siap',
        }
        data.update(changes)
        from django.core.files.uploadedfile import SimpleUploadedFile
        files = {
            'transkrip': SimpleUploadedFile('transkrip.txt', transcript_content),
            'tanda_tangan': SimpleUploadedFile(
                'sign.png',
                base64.b64decode(
                    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
                ),
                content_type='image/png',
            ),
        } if include_files else {}
        return ReplacementCandidateForm(data=data, files=files, offer=offer, candidate=self.candidate)

    def submitted_offer(self):
        offer = accept_offer(offer_id=self.create_offer().pk, candidate=self.candidate)
        form = self.candidate_form(offer)
        self.assertTrue(form.is_valid(), form.errors)
        submit_offer_registration(
            offer_id=offer.pk, candidate=self.candidate, registration_form=form,
        )
        return AslabOffer.objects.get(pk=offer.pk)

    def test_activation_promotes_candidate_and_links_same_slot(self):
        offer = self.submitted_offer()

        assignment = activate_replacement(
            offer_id=offer.pk, actor=self.laboran, active_date=date(2026, 9, 5),
        )

        self.candidate.refresh_from_db()
        self.slot.refresh_from_db()
        self.replacement.refresh_from_db()
        offer.refresh_from_db()
        self.assertEqual(assignment.slot, self.slot)
        self.assertEqual(assignment.menggantikan, self.replacement.outgoing_assignment)
        self.assertEqual(assignment.mulai_pada, date(2026, 9, 5))
        self.assertEqual(assignment.status, AslabAssignment.STATUS_ACTIVE)
        self.assertEqual(self.candidate.role, 'asisten_lab')
        self.assertEqual(self.slot.status, AslabSlot.STATUS_ACTIVE)
        self.assertEqual(self.replacement.status, AslabReplacement.STATUS_ACTIVE)
        self.assertEqual(self.replacement.incoming_assignment, assignment)
        self.assertEqual(offer.status, AslabOffer.STATUS_VERIFIED)
        self.assertEqual(offer.registration.status, 'diterima')

    def test_activation_rejects_invalid_state_actor_and_date_without_partial_changes(self):
        offer = self.submitted_offer()
        invalid_actor = self.user('BAD-ACT', 'Bad Actor', 'mahasiswa')
        for actor, active_date, message in [
            (invalid_actor, date(2026, 9, 5), 'laboran'),
            (self.laboran, date(2026, 8, 31), 'berakhir'),
            (self.laboran, date(2027, 1, 1), 'periode'),
        ]:
            with self.subTest(message=message):
                with self.assertRaisesMessage(ValidationError, message):
                    activate_replacement(
                        offer_id=offer.pk, actor=actor, active_date=active_date,
                    )
        self.assertFalse(AslabAssignment.objects.filter(menggantikan=self.replacement.outgoing_assignment).exists())
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.role, 'mahasiswa')

    def test_activation_locks_replacement_before_slot_and_offer(self):
        offer = self.submitted_offer()

        with CaptureQueriesContext(connection) as queries:
            activate_replacement(
                offer_id=offer.pk, actor=self.laboran, active_date=date(2026, 9, 5),
            )

        locking_sql = [
            query['sql'].lower() for query in queries.captured_queries
            if 'for update' in query['sql'].lower()
        ]
        replacement_table = AslabReplacement._meta.db_table.lower()
        slot_table = AslabSlot._meta.db_table.lower()
        offer_table = AslabOffer._meta.db_table.lower()
        replacement_index = next(i for i, sql in enumerate(locking_sql) if replacement_table in sql)
        slot_index = next(i for i, sql in enumerate(locking_sql) if slot_table in sql)
        offer_index = next(i for i, sql in enumerate(locking_sql) if offer_table in sql)
        self.assertLess(replacement_index, slot_index)
        self.assertLess(slot_index, offer_index)

    def test_submit_forces_links_identity_and_revision_reuses_row(self):
        offer = accept_offer(offer_id=self.create_offer().pk, candidate=self.candidate)
        form = self.candidate_form(offer)
        self.assertTrue(form.is_valid(), form.errors)
        registration = submit_offer_registration(
            offer_id=offer.pk, candidate=self.candidate, registration_form=form,
        )
        offer.refresh_from_db(); self.replacement.refresh_from_db(); self.candidate.refresh_from_db()
        self.assertEqual(registration.nama, self.candidate.nama_pengguna)
        self.assertEqual(registration.nim, self.candidate.nim_nik)
        self.assertEqual(registration.matkul, self.course)
        self.assertEqual(registration.periode, self.period)
        self.assertEqual(registration.jenis, PendaftaranAsleb.JENIS_REPLACEMENT)
        self.assertEqual(offer.status, AslabOffer.STATUS_SUBMITTED)
        self.assertEqual(self.replacement.status, AslabReplacement.STATUS_WAITING_VERIFICATION)
        self.assertEqual(self.candidate.role, 'mahasiswa')

        return_offer_for_revision(offer_id=offer.pk, actor=self.laboran, notes='Perbaiki rekening')
        offer.refresh_from_db(); self.replacement.refresh_from_db()
        self.assertEqual(offer.registration_id, registration.pk)
        self.assertIsNone(offer.submitted_at)
        revised = self.candidate_form(offer)
        self.assertTrue(revised.is_valid(), revised.errors)
        result = submit_offer_registration(
            offer_id=offer.pk, candidate=self.candidate, registration_form=revised,
        )
        self.assertEqual(result.pk, registration.pk)

    def test_submit_revalidates_manipulated_same_pk_form_against_canonical_slot(self):
        offer = accept_offer(offer_id=self.create_offer().pk, candidate=self.candidate)
        wrong_course = MataKuliahAsleb.objects.create(
            kode='ADV02', kode_mk='ADV02', nama='Adversarial Course', dosen='Dosen', kelas='TIF-02')
        wrong_slot = AslabSlot.objects.create(
            periode=self.period, matkul=wrong_course, nomor=1, status=AslabSlot.STATUS_VACANT)
        manipulated_offer = AslabOffer.objects.get(pk=offer.pk)
        manipulated_replacement = AslabReplacement.objects.get(pk=self.replacement.pk)
        manipulated_replacement.slot = wrong_slot
        manipulated_offer.replacement = manipulated_replacement
        form = self.candidate_form(
            manipulated_offer,
            matkul=wrong_course.pk,
            transcript_content=b'ADV02 Adversarial Course Nilai A\nOFF01 Offer Test Nilai C',
        )
        self.assertTrue(form.is_valid(), form.errors)

        with self.assertRaisesMessage(ValidationError, 'valid'):
            submit_offer_registration(
                offer_id=offer.pk, candidate=self.candidate, registration_form=form)

        offer.refresh_from_db()
        self.replacement.refresh_from_db()
        self.assertEqual(offer.status, AslabOffer.STATUS_ACCEPTED_INCOMPLETE)
        self.assertIsNone(offer.registration_id)
        self.assertEqual(self.replacement.status, AslabReplacement.STATUS_COMPLETING_DATA)
        self.assertFalse(PendaftaranAsleb.objects.filter(replacement_process=self.replacement).exists())

    def test_forms_filter_candidates_reject_tampering_and_require_files_payment_grade(self):
        unverified = self.user('UNV-OFF', 'Unverified', 'mahasiswa', verified=False)
        offer_form = DirectOfferForm(replacement=self.replacement, actor=self.laboran)
        self.assertIn(self.candidate, offer_form.fields['candidate'].queryset)
        self.assertNotIn(unverified, offer_form.fields['candidate'].queryset)
        offer = accept_offer(offer_id=self.create_offer().pk, candidate=self.candidate)
        wrong_course = MataKuliahAsleb.objects.create(
            kode='WRONG01', kode_mk='WR01', nama='Wrong', dosen='D', kelas='X')
        form = self.candidate_form(offer, matkul=wrong_course.pk, rekening='abc', nilai_transkrip='C')
        self.assertFalse(form.is_valid())
        self.assertIn('matkul', form.errors)
        self.assertIn('rekening', form.errors)

        missing = self.candidate_form(offer, include_files=False, rekening='', nama_pemilik_rekening='')
        self.assertFalse(missing.is_valid())
        self.assertIn('transkrip', missing.errors)
        self.assertIn('tanda_tangan', missing.errors)
        self.assertIn('rekening', missing.errors)
        self.assertIn('nama_pemilik_rekening', missing.errors)

        failing_grade = self.candidate_form(
            offer, transcript_content=b'OFF01 Offer Test Nilai C', nilai_transkrip='A')
        self.assertFalse(failing_grade.is_valid())
        self.assertIn('transkrip', failing_grade.errors)

    def test_return_revision_requires_authorization_notes_and_submitted_offer(self):
        offer = self.create_offer()
        for actor, notes, message in [(self.candidate, 'x', 'laboran'), (self.laboran, '', 'Catatan')]:
            with self.assertRaisesMessage(ValidationError, message):
                return_offer_for_revision(offer_id=offer.pk, actor=actor, notes=notes)


class TerminationServiceTests(TestCase):
    def setUp(self):
        self.period = PeriodeAsleb.objects.create(
            tahun=2026, semester=2, mulai=date(2026, 7, 1), selesai=date(2026, 12, 31),
            pendaftaran_mulai=date(2026, 7, 1), pendaftaran_selesai=date(2026, 7, 30),
        )
        self.course = MataKuliahAsleb.objects.create(
            kode='TERM_TIF01', kode_mk='TERM01', nama='Terminasi Test',
            dosen='Dosen Test', kelas='TIF-01',
        )
        self.slot = AslabSlot.objects.create(
            periode=self.period, matkul=self.course, nomor=1,
        )
        self.student = self.create_user('10001', 'Aslab Keluar', 'asisten_lab')
        self.laboran = self.create_user('LAB01', 'Laboran', 'laboran')
        self.asleb = Asleb.objects.create(
            nama=self.student.nama_pengguna, nim=self.student.nim_nik, no_hp='08123',
            email=self.student.email, program_studi='TI', semester=5, status='aktif',
            periode_aktif=self.period, tanggal_bergabung=date(2026, 7, 10),
        )
        self.assignment = AslabAssignment.objects.create(
            slot=self.slot, asleb=self.asleb, mulai_pada=date(2026, 7, 10),
            status=AslabAssignment.STATUS_ACTIVE,
        )

    def create_user(self, nim, name, role):
        return Pengguna.objects.create(
            nama_pengguna=name, nim_nik=nim, email=f'{nim.lower()}@example.com',
            password='secret', no_hp='08123', alamat='Jakarta', fakultas='FTI',
            prodi='TI', gender='laki_laki', role=role,
        )

    def end(self, **overrides):
        values = {
            'assignment_id': self.assignment.pk,
            'actor': self.laboran,
            'reason_type': 'resignation',
            'reason': 'Tidak dapat melanjutkan tugas',
            'effective_date': date(2026, 10, 15),
        }
        values.update(overrides)
        return end_assignment_for_replacement(**values)

    def test_end_assignment_updates_records_and_opens_replacement(self):
        result = self.end()

        self.assignment.refresh_from_db()
        self.slot.refresh_from_db()
        self.asleb.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(self.assignment.status, AslabAssignment.STATUS_RESIGNED)
        self.assertEqual(self.assignment.berakhir_pada, date(2026, 10, 15))
        self.assertEqual(self.assignment.alasan_berakhir, 'Tidak dapat melanjutkan tugas')
        self.assertEqual(self.assignment.diakhiri_oleh, self.laboran)
        self.assertIsNone(self.assignment.active_slot_id)
        self.assertEqual(self.slot.status, AslabSlot.STATUS_VACANT)
        self.assertEqual(self.asleb.status, 'nonaktif')
        self.assertEqual(self.student.role, 'mahasiswa')
        self.assertEqual(result.outgoing_assignment, self.assignment)
        self.assertEqual(result.transfer_month, date(2026, 10, 1))
        self.assertEqual(result.method, AslabReplacement.METHOD_UNDECIDED)
        audit = AslabReplacementAudit.objects.get(replacement=result)
        self.assertEqual(audit.action, 'assignment_ended')
        self.assertEqual(audit.actor, self.laboran)
        self.assertEqual(audit.previous_state, AslabAssignment.STATUS_ACTIVE)
        self.assertEqual(audit.new_state, AslabAssignment.STATUS_RESIGNED)
        self.assertEqual(
            audit.metadata['replacement_status'],
            AslabReplacement.STATUS_WAITING_ACTION,
        )
        self.assertFalse(PengalamanPengguna.objects.filter(pengguna=self.student).exists())

    def test_dismissal_and_other_map_to_terminated(self):
        for reason_type in ('dismissal', 'other'):
            with self.subTest(reason_type=reason_type):
                assignment = self.assignment
                if reason_type == 'other':
                    slot = AslabSlot.objects.create(periode=self.period, matkul=self.course, nomor=2)
                    assignment = AslabAssignment.objects.create(
                        slot=slot, asleb=self.asleb, mulai_pada=date(2026, 7, 10),
                        status=AslabAssignment.STATUS_ACTIVE,
                    )
                self.end(assignment_id=assignment.pk, reason_type=reason_type)
                assignment.refresh_from_db()
                self.assertEqual(assignment.status, AslabAssignment.STATUS_TERMINATED)

    def test_other_active_assignment_preserves_person_access(self):
        other_course = MataKuliahAsleb.objects.create(
            kode='TERM_TIF02', kode_mk='TERM02', nama='Terminasi Test 2',
            dosen='Dosen Test', kelas='TIF-02',
        )
        other_slot = AslabSlot.objects.create(periode=self.period, matkul=other_course, nomor=1)
        AslabAssignment.objects.create(
            slot=other_slot, asleb=self.asleb, mulai_pada=date(2026, 7, 10),
            status=AslabAssignment.STATUS_ACTIVE,
        )

        self.end()

        self.asleb.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(self.asleb.status, 'aktif')
        self.assertEqual(self.student.role, 'asisten_lab')

    def test_rejects_invalid_input_without_partial_updates(self):
        invalid_cases = [
            ({'reason': '   '}, 'Alasan'),
            ({'reason_type': 'retirement'}, 'Jenis alasan'),
            ({'method': 'auction'}, 'Metode'),
            ({'effective_date': date(2026, 6, 30)}, 'periode'),
            ({'effective_date': date(2027, 1, 1)}, 'periode'),
            ({'effective_date': date(2026, 7, 9)}, 'mulai'),
            ({'actor': self.student}, 'laboran'),
            ({'actor': None}, 'laboran'),
        ]
        for overrides, message in invalid_cases:
            with self.subTest(overrides=overrides):
                with self.assertRaisesMessage(ValidationError, message):
                    self.end(**overrides)
                self.assignment.refresh_from_db()
                self.slot.refresh_from_db()
                self.assertEqual(self.assignment.status, AslabAssignment.STATUS_ACTIVE)
                self.assertEqual(self.slot.status, AslabSlot.STATUS_ACTIVE)
                self.assertFalse(AslabReplacement.objects.exists())

    def test_rejects_datetime_as_effective_date(self):
        with self.assertRaisesMessage(ValidationError, 'Tanggal efektif tidak valid'):
            self.end(effective_date=datetime(2026, 10, 15, 8, 30))

        self.assignment.refresh_from_db()
        self.slot.refresh_from_db()
        self.assertEqual(self.assignment.status, AslabAssignment.STATUS_ACTIVE)
        self.assertEqual(self.slot.status, AslabSlot.STATUS_ACTIVE)
        self.assertFalse(AslabReplacement.objects.exists())

    def test_second_termination_is_rejected_without_duplicate(self):
        self.end()

        with self.assertRaisesMessage(ValidationError, 'sudah tidak aktif'):
            self.end()

        self.assertEqual(AslabReplacement.objects.count(), 1)
        self.assertEqual(AslabReplacementAudit.objects.count(), 1)

    def test_legacy_service_rejects_ambiguous_active_assignments_without_mutation(self):
        other_course = MataKuliahAsleb.objects.create(
            kode='LEGACY_TIF02', kode_mk='LEG02', nama='Legacy Test 2',
            dosen='Dosen Test', kelas='TIF-02',
        )
        other_slot = AslabSlot.objects.create(periode=self.period, matkul=other_course, nomor=1)
        other_assignment = AslabAssignment.objects.create(
            slot=other_slot, asleb=self.asleb, mulai_pada=date(2026, 7, 10),
            status=AslabAssignment.STATUS_ACTIVE,
        )

        with self.assertRaisesMessage(ValidationError, 'beberapa penugasan aktif'):
            end_single_active_assignment_for_replacement(
                asleb_id=self.asleb.pk,
                actor=self.laboran,
                reason_type='dismissal',
                reason='Pelanggaran aturan',
                effective_date=date(2026, 10, 15),
            )

        self.assignment.refresh_from_db()
        other_assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, AslabAssignment.STATUS_ACTIVE)
        self.assertEqual(other_assignment.status, AslabAssignment.STATUS_ACTIVE)
        self.assertFalse(AslabReplacement.objects.exists())

    def test_missing_assignment_is_clean_validation(self):
        with self.assertRaisesMessage(ValidationError, 'tidak ditemukan'):
            self.end(assignment_id=999999)

        self.assertFalse(AslabReplacement.objects.exists())

    def test_failure_rolls_back_every_update(self):
        with patch.object(AslabReplacementAudit.objects, 'create', side_effect=DatabaseError('boom')):
            with self.assertRaises(DatabaseError):
                self.end()

        self.assignment.refresh_from_db()
        self.slot.refresh_from_db()
        self.asleb.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(self.assignment.status, AslabAssignment.STATUS_ACTIVE)
        self.assertEqual(self.slot.status, AslabSlot.STATUS_ACTIVE)
        self.assertEqual(self.asleb.status, 'aktif')
        self.assertEqual(self.student.role, 'asisten_lab')
        self.assertFalse(AslabReplacement.objects.exists())

    def test_existing_history_and_honor_are_preserved(self):
        experience = PengalamanPengguna.objects.create(
            pengguna=self.student, kategori='pengalaman', jabatan='Riwayat lama',
            organisasi='Organisasi lama',
            tanggal_mulai=date(2025, 1, 1), masih_berjalan=True,
        )
        honor = HonorAsleb.objects.create(
            asleb=self.asleb, bulan=date(2026, 7, 1), jumlah_praktikum=1,
            total_pertemuan=1, jumlah=49000,
        )

        self.end()

        self.assertTrue(PengalamanPengguna.objects.filter(pk=experience.pk).exists())
        self.assertTrue(HonorAsleb.objects.filter(pk=honor.pk).exists())
        self.assertEqual(PengalamanPengguna.objects.filter(pengguna=self.student).count(), 1)

    def test_termination_holds_existing_effective_and_future_period_honor(self):
        prior = HonorAsleb.objects.create(
            asleb=self.asleb, bulan=date(2026, 9, 1), jumlah=49000,
        )
        effective = HonorAsleb.objects.create(
            asleb=self.asleb, bulan=date(2026, 10, 1), jumlah=49000,
        )
        future = HonorAsleb.objects.create(
            asleb=self.asleb, bulan=date(2026, 12, 1), jumlah=49000,
        )

        replacement = self.end()

        self.assertFalse(HonorReassignment.objects.filter(honor=prior).exists())
        self.assertEqual(
            set(HonorReassignment.objects.filter(replacement=replacement).values_list(
                'honor_id', flat=True,
            )),
            {effective.pk, future.pk},
        )
        self.assertFalse(
            HonorReassignment.objects.filter(replacement=replacement).exclude(
                status=HonorReassignment.STATUS_HELD,
            ).exists()
        )


@skipUnless(connection.vendor == 'mysql', 'MySQL row-lock behavior required')
class TerminationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.period = PeriodeAsleb.objects.create(
            tahun=2026, semester=2, mulai=date(2026, 7, 1), selesai=date(2026, 12, 31),
            pendaftaran_mulai=date(2026, 7, 1), pendaftaran_selesai=date(2026, 7, 30),
        )
        self.course = self.create_course('CONC01', 'Concurrency 1')
        self.laboran = self.create_user('LAB-CONC', 'Laboran Concurrent', 'laboran')
        self.student = self.create_user('STU-CONC', 'Aslab Concurrent', 'asisten_lab')
        self.asleb = Asleb.objects.create(
            nama=self.student.nama_pengguna, nim=self.student.nim_nik, no_hp='08123',
            email=self.student.email, program_studi='TI', semester=5, status='aktif',
            periode_aktif=self.period, tanggal_bergabung=date(2026, 7, 1),
        )
        self.assignment = self.create_assignment(self.course, 1)

    def create_user(self, nim, name, role):
        return Pengguna.objects.create(
            nama_pengguna=name, nim_nik=nim, email=f'{nim.lower()}@example.com',
            password='secret', no_hp='08123', alamat='Jakarta', fakultas='FTI',
            prodi='TI', gender='laki_laki', role=role,
        )

    def create_course(self, code, name):
        return MataKuliahAsleb.objects.create(
            kode=code, kode_mk=code, nama=name, dosen='Dosen Test', kelas='TIF-01',
        )

    def create_assignment(self, course, number):
        slot = AslabSlot.objects.create(periode=self.period, matkul=course, nomor=number)
        return AslabAssignment.objects.create(
            slot=slot, asleb=self.asleb, mulai_pada=date(2026, 7, 1),
            status=AslabAssignment.STATUS_ACTIVE,
        )

    def terminate_in_thread(self, assignment_id, barrier, results):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            replacement = end_assignment_for_replacement(
                assignment_id=assignment_id, actor=Pengguna.objects.get(pk=self.laboran.pk),
                reason_type='dismissal', reason='Concurrent termination',
                effective_date=date(2026, 10, 15),
            )
            results.put(('success', replacement.pk))
        except (ValidationError, IntegrityError) as exc:
            results.put(('clean_error', exc.__class__.__name__))
        except Exception as exc:
            results.put(('unexpected', repr(exc)))
        finally:
            close_old_connections()

    def test_simultaneous_same_assignment_creates_one_replacement(self):
        barrier = Barrier(2)
        results = Queue()
        threads = [
            Thread(target=self.terminate_in_thread, args=(self.assignment.pk, barrier, results))
            for _ in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        outcomes = [results.get(timeout=2)[0] for _ in threads]
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertCountEqual(outcomes, ['success', 'clean_error'])
        self.assertEqual(AslabReplacement.objects.count(), 1)

    def test_simultaneous_different_assignments_serialize_without_deadlock(self):
        second = self.create_assignment(self.create_course('CONC02', 'Concurrency 2'), 1)
        barrier = Barrier(2)
        results = Queue()
        threads = [
            Thread(target=self.terminate_in_thread, args=(assignment_id, barrier, results))
            for assignment_id in (self.assignment.pk, second.pk)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        outcomes = [results.get(timeout=2)[0] for _ in threads]
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(outcomes.count('success'), 2, outcomes)
        self.assertEqual(AslabReplacement.objects.count(), 2)
        self.asleb.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(self.asleb.status, 'nonaktif')
        self.assertEqual(self.student.role, 'mahasiswa')

    def test_legacy_invariant_is_rechecked_after_waiting_for_person_lock(self):
        person_locked = Event()
        allow_insert = Event()
        results = Queue()

        def add_assignment_while_holding_person_lock():
            close_old_connections()
            try:
                with transaction.atomic():
                    Asleb.objects.select_for_update().get(pk=self.asleb.pk)
                    person_locked.set()
                    allow_insert.wait(timeout=10)
                    course = self.create_course('CONC03', 'Concurrency 3')
                    self.create_assignment(course, 1)
                results.put(('inserted', None))
            except Exception as exc:
                results.put(('unexpected', repr(exc)))
            finally:
                close_old_connections()

        def terminate_legacy():
            close_old_connections()
            try:
                end_single_active_assignment_for_replacement(
                    asleb_id=self.asleb.pk,
                    actor=Pengguna.objects.get(pk=self.laboran.pk),
                    reason_type='dismissal', reason='Legacy concurrent termination',
                    effective_date=date(2026, 10, 15),
                )
                results.put(('unexpected_success', None))
            except ValidationError:
                results.put(('clean_error', None))
            except Exception as exc:
                results.put(('unexpected', repr(exc)))
            finally:
                close_old_connections()

        inserter = Thread(target=add_assignment_while_holding_person_lock)
        inserter.start()
        self.assertTrue(person_locked.wait(timeout=10))
        terminator = Thread(target=terminate_legacy)
        terminator.start()
        allow_insert.set()
        inserter.join(timeout=15)
        terminator.join(timeout=15)

        outcomes = [results.get(timeout=2)[0] for _ in range(2)]
        self.assertFalse(inserter.is_alive() or terminator.is_alive())
        self.assertCountEqual(outcomes, ['inserted', 'clean_error'])
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, AslabAssignment.STATUS_ACTIVE)
        self.assertFalse(AslabReplacement.objects.exists())


@skipUnless(connection.vendor == 'mysql', 'MySQL row-lock behavior required')
class DirectOfferConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.period = PeriodeAsleb.objects.create(
            tahun=2026, semester=2, mulai=date(2026, 7, 1), selesai=date(2026, 12, 31),
            pendaftaran_mulai=date(2026, 7, 1), pendaftaran_selesai=date(2026, 7, 30))
        self.laboran = self.user('LAB-RACE', 'Laboran Race', 'laboran')
        self.candidate = self.user('STU-RACE', 'Candidate Race', 'mahasiswa')
        self.replacement = self.make_replacement('RACE01', 1)

    def user(self, nim, name, role):
        return Pengguna.objects.create(
            nama_pengguna=name, nim_nik=nim, email=f'{nim.lower()}@example.com', password='secret',
            no_hp='08123', alamat='Jakarta', fakultas='FTI', prodi='TI', gender='laki_laki',
            role=role)

    def make_replacement(self, code, number):
        course = MataKuliahAsleb.objects.create(
            kode=code, kode_mk=code, nama=f'Course {code}', dosen='Dosen', kelas=code)
        slot = AslabSlot.objects.create(
            periode=self.period, matkul=course, nomor=number, status=AslabSlot.STATUS_VACANT)
        old = Asleb.objects.create(
            nama=f'Old {code}', nim=f'OLD-{code}', no_hp='081',
            email=f'old-{code.lower()}@example.com', program_studi='TI', semester=5,
            status='nonaktif', periode_aktif=self.period, tanggal_bergabung=date(2026, 7, 1))
        assignment = AslabAssignment.objects.create(
            slot=slot, asleb=old, mulai_pada=date(2026, 7, 1),
            berakhir_pada=date(2026, 9, 1), status=AslabAssignment.STATUS_RESIGNED)
        return AslabReplacement.objects.create(
            slot=slot, outgoing_assignment=assignment, effective_date=date(2026, 9, 1),
            transfer_month=date(2026, 9, 1), created_by=self.laboran)

    def offer(self, replacement=None, candidate=None, deadline=None):
        return create_direct_offer(
            replacement_id=(replacement or self.replacement).pk,
            candidate_id=(candidate or self.candidate).pk,
            deadline=deadline or timezone.now() + timezone.timedelta(days=1),
            actor=self.laboran)

    def form(self, offer, candidate):
        from django.core.files.uploadedfile import SimpleUploadedFile
        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
        data = {
            'nama': candidate.nama_pengguna, 'nim': candidate.nim_nik, 'no_hp': candidate.no_hp,
            'email': candidate.email, 'program_studi': candidate.prodi, 'semester': 5,
            'matkul': offer.replacement.slot.matkul_id, 'metode_rekening': 'bni',
            'rekening': '123456', 'nama_pemilik_rekening': candidate.nama_pengguna,
            'nilai_transkrip': 'A', 'alasan': 'Siap',
        }
        files = {
            'transkrip': SimpleUploadedFile(
                'transkrip.txt',
                f'{offer.replacement.slot.matkul.kode_mk} Nilai A'.encode()),
            'tanda_tangan': SimpleUploadedFile('sign.png', png, content_type='image/png'),
        }
        return ReplacementCandidateForm(data=data, files=files, offer=offer, candidate=candidate)

    def run_race(self, operations):
        barrier = Barrier(2)
        results = Queue()

        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                results.put(('success', operation()))
            except (ValidationError, IntegrityError) as exc:
                results.put(('clean_error', exc.__class__.__name__))
            except Exception as exc:
                results.put(('unexpected', repr(exc)))
            finally:
                close_old_connections()

        threads = [Thread(target=run, args=(operation,)) for operation in operations]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        outcomes = [results.get(timeout=2) for _ in threads]
        self.assertFalse(any(thread.is_alive() for thread in threads), outcomes)
        self.assertFalse(any(kind == 'unexpected' for kind, _value in outcomes), outcomes)
        return outcomes

    def test_concurrent_offers_same_replacement_create_one_live_offer(self):
        other = self.user('STU-RACE-2', 'Candidate Race 2', 'mahasiswa')
        deadline = timezone.now() + timezone.timedelta(days=1)
        outcomes = self.run_race([
            lambda candidate_id=candidate_id: create_direct_offer(
                replacement_id=self.replacement.pk, candidate_id=candidate_id,
                deadline=deadline, actor=Pengguna.objects.get(pk=self.laboran.pk))
            for candidate_id in (self.candidate.pk, other.pk)
        ])
        self.assertCountEqual([kind for kind, _ in outcomes], ['success', 'clean_error'])
        self.assertEqual(AslabOffer.objects.filter(replacement=self.replacement).count(), 1)

    def test_same_candidate_concurrent_offers_in_period_create_one(self):
        second = self.make_replacement('RACE02', 1)
        deadline = timezone.now() + timezone.timedelta(days=1)
        outcomes = self.run_race([
            lambda replacement_id=replacement_id: create_direct_offer(
                replacement_id=replacement_id, candidate_id=self.candidate.pk,
                deadline=deadline, actor=Pengguna.objects.get(pk=self.laboran.pk))
            for replacement_id in (self.replacement.pk, second.pk)
        ])
        self.assertCountEqual([kind for kind, _ in outcomes], ['success', 'clean_error'])
        self.assertEqual(AslabOffer.objects.filter(candidate=self.candidate).count(), 1)

    def test_accept_racing_expiry_has_one_terminal_transition(self):
        deadline = timezone.now() + timezone.timedelta(days=1)
        offer = self.offer(deadline=deadline)
        outcomes = self.run_race([
            lambda: accept_offer(
                offer_id=offer.pk, candidate=Pengguna.objects.get(pk=self.candidate.pk)).status,
            lambda: expire_due_offers(now=deadline),
        ])
        offer.refresh_from_db()
        self.replacement.refresh_from_db()
        self.assertIn(
            (offer.status, self.replacement.status),
            {
                (AslabOffer.STATUS_ACCEPTED_INCOMPLETE,
                 AslabReplacement.STATUS_COMPLETING_DATA),
                (AslabOffer.STATUS_EXPIRED,
                 AslabReplacement.STATUS_WAITING_ACTION),
            },
        )
        terminal_audits = AslabReplacementAudit.objects.filter(
            replacement=self.replacement,
            action__in=['offer_accepted', 'offer_expired'],
        )
        self.assertEqual(terminal_audits.count(), 1)
        expected_action = (
            'offer_accepted'
            if offer.status == AslabOffer.STATUS_ACCEPTED_INCOMPLETE
            else 'offer_expired'
        )
        self.assertEqual(terminal_audits.get().action, expected_action)
        self.assertGreaterEqual(sum(kind == 'success' for kind, _ in outcomes), 1)

    def test_concurrent_submit_creates_one_registration(self):
        offer = accept_offer(offer_id=self.offer().pk, candidate=self.candidate)

        def submit():
            canonical_offer = AslabOffer.objects.select_related(
                'replacement__slot__matkul').get(pk=offer.pk)
            candidate = Pengguna.objects.get(pk=self.candidate.pk)
            return submit_offer_registration(
                offer_id=offer.pk, candidate=candidate,
                registration_form=self.form(canonical_offer, candidate)).pk

        outcomes = self.run_race([submit, submit])
        self.assertCountEqual([kind for kind, _ in outcomes], ['success', 'clean_error'])
        self.assertEqual(PendaftaranAsleb.objects.filter(
            replacement_process=self.replacement).count(), 1)

    def test_submit_racing_return_preserves_single_registration_link(self):
        offer = accept_offer(offer_id=self.offer().pk, candidate=self.candidate)

        def submit():
            canonical_offer = AslabOffer.objects.select_related(
                'replacement__slot__matkul').get(pk=offer.pk)
            candidate = Pengguna.objects.get(pk=self.candidate.pk)
            return submit_offer_registration(
                offer_id=offer.pk, candidate=candidate,
                registration_form=self.form(canonical_offer, candidate)).pk

        def revise():
            return return_offer_for_revision(
                offer_id=offer.pk, actor=Pengguna.objects.get(pk=self.laboran.pk),
                notes='Concurrent revision').status

        outcomes = self.run_race([submit, revise])
        offer.refresh_from_db()
        self.replacement.refresh_from_db()
        self.assertEqual(PendaftaranAsleb.objects.filter(
            replacement_process=self.replacement).count(), 1)
        self.assertIsNotNone(offer.registration_id)
        self.assertIn(offer.status, {
            AslabOffer.STATUS_SUBMITTED, AslabOffer.STATUS_ACCEPTED_INCOMPLETE})
        self.assertFalse(any(kind == 'unexpected' for kind, _ in outcomes), outcomes)

    def test_concurrent_activation_creates_one_incoming_assignment(self):
        offer = accept_offer(offer_id=self.offer().pk, candidate=self.candidate)
        canonical_offer = AslabOffer.objects.select_related(
            'replacement__slot__matkul').get(pk=offer.pk)
        form = self.form(canonical_offer, self.candidate)
        self.assertTrue(form.is_valid(), form.errors)
        submit_offer_registration(
            offer_id=offer.pk, candidate=self.candidate, registration_form=form,
        )

        outcomes = self.run_race([
            lambda: activate_replacement(
                offer_id=offer.pk,
                actor=Pengguna.objects.get(pk=self.laboran.pk),
                active_date=date(2026, 9, 1),
            ).pk,
            lambda: activate_replacement(
                offer_id=offer.pk,
                actor=Pengguna.objects.get(pk=self.laboran.pk),
                active_date=date(2026, 9, 1),
            ).pk,
        ])

        self.assertCountEqual([kind for kind, _ in outcomes], ['success', 'clean_error'])
        self.assertEqual(AslabAssignment.objects.filter(
            menggantikan=self.replacement.outgoing_assignment,
        ).count(), 1)

    def test_activation_racing_return_has_consistent_terminal_pair_without_deadlock(self):
        offer = accept_offer(offer_id=self.offer().pk, candidate=self.candidate)
        canonical_offer = AslabOffer.objects.select_related(
            'replacement__slot__matkul').get(pk=offer.pk)
        form = self.form(canonical_offer, self.candidate)
        self.assertTrue(form.is_valid(), form.errors)
        submit_offer_registration(
            offer_id=offer.pk, candidate=self.candidate, registration_form=form,
        )

        outcomes = self.run_race([
            lambda: activate_replacement(
                offer_id=offer.pk,
                actor=Pengguna.objects.get(pk=self.laboran.pk),
                active_date=date(2026, 9, 1),
            ).pk,
            lambda: return_offer_for_revision(
                offer_id=offer.pk,
                actor=Pengguna.objects.get(pk=self.laboran.pk),
                notes='Perbaiki data bersamaan aktivasi',
            ).status,
        ])

        offer.refresh_from_db()
        self.replacement.refresh_from_db()
        self.assertFalse(any(kind == 'unexpected' for kind, _ in outcomes), outcomes)
        self.assertIn(
            (offer.status, self.replacement.status),
            {
                (AslabOffer.STATUS_VERIFIED, AslabReplacement.STATUS_ACTIVE),
                (AslabOffer.STATUS_ACCEPTED_INCOMPLETE,
                 AslabReplacement.STATUS_COMPLETING_DATA),
            },
        )
