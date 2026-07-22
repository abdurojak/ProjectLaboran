from datetime import date
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.test import TestCase

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
from .replacement_services import end_assignment_for_replacement


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
        self.assertEqual(audit.new_state, AslabReplacement.STATUS_WAITING_ACTION)
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

    def test_second_termination_is_rejected_without_duplicate(self):
        self.end()

        with self.assertRaisesMessage(ValidationError, 'sudah tidak aktif'):
            self.end()

        self.assertEqual(AslabReplacement.objects.count(), 1)
        self.assertEqual(AslabReplacementAudit.objects.count(), 1)

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
