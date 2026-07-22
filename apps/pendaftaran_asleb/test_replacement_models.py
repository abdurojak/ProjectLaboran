from datetime import date
from importlib import import_module
from io import StringIO

from django.apps import apps as django_apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
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

    def test_active_slot_id_move_partial_save_moves_guard(self):
        assignment = self.create_assignment(self.first_asleb)
        other_slot = AslabSlot.objects.create(
            periode=self.period,
            matkul=self.course,
            nomor=2,
        )

        assignment.slot_id = other_slot.pk
        update_fields = ['slot_id']
        assignment.save(update_fields=update_fields)

        assignment.refresh_from_db()
        self.assertEqual(assignment.slot_id, other_slot.pk)
        self.assertEqual(assignment.active_slot_id, other_slot.pk)
        self.assertEqual(update_fields, ['slot_id'])

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


class AslabBackfillTests(TestCase):
    def setUp(self):
        self.migration = import_module(
            'apps.pendaftaran_asleb.migrations.0017_backfill_aslab_assignments'
        )
        self.period = PeriodeAsleb.objects.create(
            tahun=2026,
            semester=2,
            mulai=date(2026, 7, 1),
            selesai=date(2026, 12, 31),
            pendaftaran_mulai=date(2026, 6, 1),
            pendaftaran_selesai=date(2026, 6, 30),
        )
        self.course = self.create_course('TEST_A', 'TIF-01')

    def create_course(self, kode, kelas):
        return MataKuliahAsleb.objects.create(
            kode=kode,
            kode_mk=kode,
            nama=f'Mata Kuliah {kode}',
            dosen='Dosen Test',
            kelas=kelas,
        )

    def create_registration(self, nim, course=None, status='diterima'):
        return PendaftaranAsleb.objects.create(
            nama=f'Pendaftar {nim}',
            nim=nim,
            no_hp='08123456789',
            program_studi='Teknik Informatika',
            semester=5,
            matkul=course or self.course,
            periode=self.period,
            status=status,
        )

    def create_active_asleb(self, nim, matkul=''):
        return Asleb.objects.create(
            nama=f'Aslab {nim}',
            nim=nim,
            no_hp='08123456789',
            program_studi='Teknik Informatika',
            matkul=matkul,
            semester=5,
            status='aktif',
            periode_aktif=self.period,
            tanggal_bergabung=self.period.mulai,
        )

    def run_backfill(self):
        with connection.schema_editor() as schema_editor:
            self.migration.backfill_aslab_assignments(django_apps, schema_editor)

    def test_exact_single_registration_creates_lowest_slot_assignment(self):
        registration = self.create_registration('10001')
        asleb = self.create_active_asleb('10001')

        self.run_backfill()

        assignment = AslabAssignment.objects.get(asleb=asleb)
        self.assertEqual(assignment.slot.nomor, 1)
        self.assertEqual(assignment.slot.matkul, self.course)
        self.assertEqual(assignment.source_pendaftaran, registration)
        self.assertEqual(assignment.active_slot_id, assignment.slot_id)
        self.assertEqual(assignment.status, 'active')
        self.assertEqual(assignment.mulai_pada, self.period.mulai)

    def test_legacy_course_string_disambiguates_only_by_exact_label(self):
        other_course = self.create_course('TEST_B', 'TIF-02')
        self.create_registration('10002')
        selected = self.create_registration('10002', other_course, 'digenerate')
        asleb = self.create_active_asleb('10002', str(other_course))

        self.run_backfill()

        self.assertEqual(
            AslabAssignment.objects.get(asleb=asleb).source_pendaftaran,
            selected,
        )

    def test_ambiguous_and_unmatched_rows_are_not_assigned(self):
        other_course = self.create_course('TEST_B', 'TIF-02')
        self.create_registration('10003')
        self.create_registration('10003', other_course)
        self.create_active_asleb('10003', 'Mata Kuliah')
        self.create_active_asleb('10004')

        self.run_backfill()

        self.assertFalse(AslabAssignment.objects.exists())
        self.assertFalse(AslabSlot.objects.exists())

    def test_capacity_is_two_and_rerun_is_idempotent(self):
        aslebs = []
        for nim in ('10005', '10006', '10007'):
            self.create_registration(nim)
            aslebs.append(self.create_active_asleb(nim))

        self.run_backfill()
        self.run_backfill()

        self.assertEqual(AslabSlot.objects.count(), 2)
        self.assertEqual(AslabAssignment.objects.count(), 2)
        self.assertEqual(
            list(AslabAssignment.objects.order_by('slot__nomor').values_list('asleb__nim', flat=True)),
            ['10005', '10006'],
        )
        self.assertFalse(AslabAssignment.objects.filter(asleb=aslebs[2]).exists())

    def test_closed_slot_is_skipped_when_allocating_lowest_free_slot(self):
        registration = self.create_registration('10008')
        asleb = self.create_active_asleb('10008')
        AslabSlot.objects.create(
            periode=self.period,
            matkul=self.course,
            nomor=1,
            status='closed',
        )

        self.run_backfill()

        assignment = AslabAssignment.objects.get(asleb=asleb)
        self.assertEqual(assignment.source_pendaftaran, registration)
        self.assertEqual(assignment.slot.nomor, 2)

    def test_vacant_slot_becomes_active_when_it_is_assigned(self):
        self.create_registration('10009')
        asleb = self.create_active_asleb('10009')
        slot = AslabSlot.objects.create(
            periode=self.period,
            matkul=self.course,
            nomor=1,
            status='vacant',
        )

        self.run_backfill()

        slot.refresh_from_db()
        self.assertEqual(slot.status, 'active')
        self.assertEqual(AslabAssignment.objects.get(asleb=asleb).slot, slot)


class AuditAslabSlotsCommandTests(AslabBackfillTests):
    def test_audit_reports_categories_without_modifying_data(self):
        other_course = self.create_course('TEST_B', 'TIF-02')
        self.create_registration('20001')
        assigned = self.create_active_asleb('20001')
        self.create_registration('20002')
        self.create_registration('20002', other_course)
        self.create_active_asleb('20002')
        self.create_active_asleb('20003')
        self.run_backfill()
        AslabAssignment.objects.filter(asleb=assigned).delete()
        before = (AslabSlot.objects.count(), AslabAssignment.objects.count())
        output = StringIO()

        call_command('audit_aslab_slots', stdout=output)

        report = output.getvalue()
        self.assertIn('AMBIGUOUS: 20002', report)
        self.assertIn('UNMATCHED: 20003', report)
        self.assertIn('MISSING_ASSIGNMENT: 20001', report)
        self.assertEqual(before, (AslabSlot.objects.count(), AslabAssignment.objects.count()))

    def test_strict_raises_when_active_legacy_row_is_unresolved(self):
        self.create_active_asleb('20004')

        with self.assertRaises(CommandError):
            call_command('audit_aslab_slots', '--strict', stdout=StringIO())

    def test_audit_reports_active_legacy_row_without_period(self):
        asleb = self.create_active_asleb('20008')
        Asleb.objects.filter(pk=asleb.pk).update(periode_aktif=None)
        output = StringIO()

        with self.assertRaises(CommandError):
            call_command('audit_aslab_slots', '--strict', stdout=output)

        self.assertIn('NO_PERIOD: 20008', output.getvalue())

    def test_audit_reports_over_capacity_and_inconsistent_occupancy(self):
        registrations = []
        for nim in ('20005', '20006', '20007'):
            registrations.append(self.create_registration(nim))
            self.create_active_asleb(nim)
        self.run_backfill()
        assignment = AslabAssignment.objects.order_by('pk').first()
        AslabAssignment.objects.filter(pk=assignment.pk).update(
            source_pendaftaran=registrations[2]
        )
        output = StringIO()

        call_command('audit_aslab_slots', stdout=output)

        report = output.getvalue()
        self.assertIn('OVER_CAPACITY: 20007', report)
        self.assertIn('INCONSISTENT_OCCUPANCY:', report)
