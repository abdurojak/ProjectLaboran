from datetime import date
from importlib import import_module

from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase

from apps.asleb.models import Asleb
from apps.pendaftaran_asleb.models import (
    AslabAssignment,
    AslabSlot,
    MataKuliahAsleb,
    PendaftaranAsleb,
    PeriodeAsleb,
)


class AslabAssignmentFoundationTests(TestCase):
    def setUp(self):
        self.period = PeriodeAsleb.objects.create(
            tahun=2026,
            semester=2,
            mulai=date(2026, 7, 1),
            selesai=date(2026, 12, 31),
            pendaftaran_mulai=date(2026, 7, 1),
            pendaftaran_selesai=date(2026, 7, 30),
        )
        self.course = MataKuliahAsleb.objects.create(
            kode='TEST_TIF01',
            kode_mk='TEST01',
            nama='Mata Kuliah Test',
            dosen='Dosen Test',
            kelas='TIF-01',
        )
        self.slot = AslabSlot.objects.create(
            periode=self.period,
            matkul=self.course,
            nomor=1,
        )
        self.first_asleb = self.create_asleb('10001', 'Aslab Pertama')
        self.second_asleb = self.create_asleb('10002', 'Aslab Kedua')

    def create_asleb(self, nim, nama):
        return Asleb.objects.create(
            nama=nama,
            nim=nim,
            no_hp='08123456789',
            program_studi='Teknik Informatika',
            semester=5,
            tanggal_bergabung=self.period.mulai,
        )

    def create_assignment(self, asleb, **overrides):
        values = {
            'slot': self.slot,
            'asleb': asleb,
            'mulai_pada': self.period.mulai,
            'status': AslabAssignment.STATUS_ACTIVE,
        }
        values.update(overrides)
        return AslabAssignment.objects.create(**values)

    def test_slot_number_must_be_one_or_two(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AslabSlot.objects.create(
                    periode=self.period,
                    matkul=self.course,
                    nomor=3,
                )

    def test_period_course_and_slot_number_are_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AslabSlot.objects.create(
                    periode=self.period,
                    matkul=self.course,
                    nomor=1,
                )

    def test_only_one_active_assignment_can_occupy_a_slot(self):
        self.create_assignment(self.first_asleb)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_assignment(self.second_asleb)

    def test_inactive_assignments_do_not_claim_active_slot_guard(self):
        first = self.create_assignment(
            self.first_asleb,
            status=AslabAssignment.STATUS_RESIGNED,
        )
        second = self.create_assignment(
            self.second_asleb,
            status=AslabAssignment.STATUS_COMPLETED,
        )

        self.assertIsNone(first.active_slot_id)
        self.assertIsNone(second.active_slot_id)

    def test_database_rejects_active_status_without_guard(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AslabAssignment.objects.bulk_create([
                    AslabAssignment(
                        slot=self.slot,
                        asleb=self.first_asleb,
                        mulai_pada=self.period.mulai,
                        status=AslabAssignment.STATUS_ACTIVE,
                    ),
                ])

    def test_database_rejects_guard_for_a_different_slot(self):
        other_slot = AslabSlot.objects.create(
            periode=self.period,
            matkul=self.course,
            nomor=2,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AslabAssignment.objects.bulk_create([
                    AslabAssignment(
                        slot=self.slot,
                        active_slot=other_slot,
                        asleb=self.first_asleb,
                        mulai_pada=self.period.mulai,
                        status=AslabAssignment.STATUS_ACTIVE,
                    ),
                ])

    def test_pending_to_active_partial_save_persists_guard(self):
        assignment = self.create_assignment(
            self.first_asleb,
            status=AslabAssignment.STATUS_PENDING,
        )

        assignment.status = AslabAssignment.STATUS_ACTIVE
        assignment.save(update_fields=['status'])

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, AslabAssignment.STATUS_ACTIVE)
        self.assertEqual(assignment.active_slot_id, self.slot.pk)

    def test_active_to_resigned_partial_save_clears_guard(self):
        assignment = self.create_assignment(self.first_asleb)

        assignment.status = AslabAssignment.STATUS_RESIGNED
        assignment.save(update_fields=('status',))

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, AslabAssignment.STATUS_RESIGNED)
        self.assertIsNone(assignment.active_slot_id)

    def test_active_slot_move_partial_save_moves_guard(self):
        assignment = self.create_assignment(self.first_asleb)
        other_slot = AslabSlot.objects.create(
            periode=self.period,
            matkul=self.course,
            nomor=2,
        )

        assignment.slot = other_slot
        update_fields = {'slot'}
        assignment.save(update_fields=update_fields)

        assignment.refresh_from_db()
        self.assertEqual(assignment.slot_id, other_slot.pk)
        self.assertEqual(assignment.active_slot_id, other_slot.pk)
        self.assertEqual(update_fields, {'slot'})

    def test_historical_ownership_is_protected(self):
        assignment = self.create_assignment(self.first_asleb)

        for obj in (self.period, self.course, self.first_asleb, self.slot):
            with self.assertRaises(ProtectedError):
                obj.delete()
        self.assertTrue(AslabAssignment.objects.filter(pk=assignment.pk).exists())

    def test_nullable_source_registration_is_set_null_on_delete(self):
        registration = PendaftaranAsleb.objects.create(
            nama='Aslab Pertama',
            nim='10001',
            no_hp='08123456789',
            program_studi='Teknik Informatika',
            semester=5,
            matkul=self.course,
            periode=self.period,
        )
        assignment = self.create_assignment(
            self.first_asleb,
            source_pendaftaran=registration,
        )

        registration.delete()
        assignment.refresh_from_db()
        self.assertIsNone(assignment.source_pendaftaran_id)


class CheckConstraintCompatibilityGuardTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migration = import_module(
            'apps.pendaftaran_asleb.migrations.0016_aslab_assignment_foundation'
        )

    @staticmethod
    def schema_editor(version, is_mariadb=False, vendor='mysql'):
        connection = type('FakeConnection', (), {
            'vendor': vendor,
            'mysql_version': version,
            'mysql_is_mariadb': is_mariadb,
        })()
        return type('FakeSchemaEditor', (), {'connection': connection})()

    def test_guard_rejects_mysql_before_check_enforcement(self):
        editor = self.schema_editor((8, 0, 15))

        with self.assertRaisesRegex(RuntimeError, 'MySQL 8.0.16 or newer'):
            self.migration.ensure_check_constraints_supported(None, editor)

    def test_guard_accepts_supported_mysql_and_mariadb(self):
        self.migration.ensure_check_constraints_supported(
            None,
            self.schema_editor((8, 0, 16)),
        )
        self.migration.ensure_check_constraints_supported(
            None,
            self.schema_editor((10, 4, 27), is_mariadb=True),
        )
