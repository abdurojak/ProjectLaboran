import base64
from datetime import date, datetime
from queue import Queue
from threading import Barrier, Event, Thread
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.asleb.models import Asleb, HonorAsleb
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
    create_direct_offer,
    decline_offer,
    end_assignment_for_replacement,
    end_single_active_assignment_for_replacement,
    expire_due_offers,
    return_offer_for_revision,
    submit_offer_registration,
)


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

        third = self.create_offer(deadline=self.now + timezone.timedelta(seconds=1))
        self.assertEqual(expire_due_offers(now=third.deadline), 1)
        self.assertEqual(expire_due_offers(now=third.deadline), 0)
        third.refresh_from_db()
        self.assertEqual(third.status, AslabOffer.STATUS_EXPIRED)

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
        with self.assertRaisesMessage(ValidationError, 'aktif'):
            self.create_offer()

    def test_offer_ownership_and_deadline_are_enforced(self):
        offer = self.create_offer(deadline=self.now + timezone.timedelta(seconds=1))
        other = self.user('OTH-OFF', 'Other', 'mahasiswa')
        with self.assertRaisesMessage(ValidationError, 'kandidat'):
            accept_offer(offer_id=offer.pk, candidate=other)
        with patch('apps.pendaftaran_asleb.replacement_services.timezone.now', return_value=offer.deadline):
            with self.assertRaisesMessage(ValidationError, 'kedaluwarsa'):
                accept_offer(offer_id=offer.pk, candidate=self.candidate)

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
