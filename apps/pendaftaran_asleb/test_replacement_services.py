from datetime import date, datetime
from queue import Queue
from threading import Barrier, Event, Thread
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase

from apps.asleb.models import Asleb, HonorAsleb
from apps.pengguna.models import PengalamanPengguna, Pengguna

from .models import (
    AslabAssignment,
    AslabReplacement,
    AslabReplacementAudit,
    AslabSlot,
    MataKuliahAsleb,
    PeriodeAsleb,
)
from .replacement_services import (
    end_assignment_for_replacement,
    end_single_active_assignment_for_replacement,
)


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
