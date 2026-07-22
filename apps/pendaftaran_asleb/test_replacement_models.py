from collections import defaultdict
from datetime import date, timedelta
from importlib import import_module
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.exceptions import FieldDoesNotExist
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.asleb.models import Asleb
from apps.pengguna.models import Pengguna
from apps.pendaftaran_asleb.models import (
    AslabAssignment,
    AslabOffer,
    AslabReplacement,
    AslabReplacementAudit,
    AslabSlot,
    LimitedReplacementOpening,
    MataKuliahAsleb,
    PendaftaranAsleb,
    PeriodeAsleb,
)
from apps.pendaftaran_asleb.admin import (
    AslabOfferAdmin,
    AslabReplacementAdmin,
    AslabReplacementAuditAdmin,
    LimitedReplacementOpeningAdmin,
)


class AslabReplacementModelTests(TestCase):
    def setUp(self):
        self.period = PeriodeAsleb.objects.create(
            tahun=2026, semester=2, mulai=date(2026, 7, 1),
            selesai=date(2026, 12, 31), pendaftaran_mulai=date(2026, 7, 1),
            pendaftaran_selesai=date(2026, 7, 30),
        )
        self.course = MataKuliahAsleb.objects.create(
            kode='REPL_TEST', kode_mk='REPL01', nama='Replacement Test',
            dosen='Dosen Test', kelas='TIF-01',
        )
        self.slot = AslabSlot.objects.create(periode=self.period, matkul=self.course, nomor=1)
        self.asleb = Asleb.objects.create(
            nama='Outgoing', nim='99001', no_hp='08123',
            program_studi='Teknik Informatika', semester=5,
            tanggal_bergabung=self.period.mulai,
        )
        self.assignment = AslabAssignment.objects.create(
            slot=self.slot, asleb=self.asleb, mulai_pada=self.period.mulai,
            status=AslabAssignment.STATUS_ACTIVE,
        )
        self.creator = self.create_user('laboran', '90001')
        self.candidate = self.create_user('mahasiswa', '90002')

    def create_user(self, role, nim):
        return Pengguna.objects.create(
            nama_pengguna=f'User {nim}', nim_nik=nim, email=f'{nim}@example.com',
            password='password', no_hp='08123', alamat='Alamat', fakultas='FTI',
            prodi='Teknik Informatika', gender='laki_laki', role=role,
        )

    def create_replacement(self, **overrides):
        values = {
            'slot': self.slot, 'outgoing_assignment': self.assignment,
            'effective_date': date(2026, 8, 15), 'transfer_month': date(2026, 8, 1),
            'created_by': self.creator,
        }
        values.update(overrides)
        return AslabReplacement.objects.create(**values)

    def create_offer(self, replacement, candidate=None, **overrides):
        values = {
            'replacement': replacement,
            'candidate': candidate or self.candidate,
            'deadline': timezone.now() + timedelta(days=3),
        }
        values.update(overrides)
        return AslabOffer.objects.create(**values)

    def test_regular_registration_defaults_to_no_replacement_links(self):
        registration = PendaftaranAsleb.objects.create(
            nama='Regular', nim='10001', no_hp='08123', program_studi='TI',
            semester=5, matkul=self.course, periode=self.period,
        )
        self.assertEqual(registration.jenis, PendaftaranAsleb.JENIS_REGULER)
        self.assertIsNone(registration.replacement_process_id)
        self.assertIsNone(registration.candidate_user_id)
        self.assertIsNone(registration.live_candidate_user_id)

    def test_database_rejects_registration_linkage_inconsistent_with_kind(self):
        replacement = self.create_replacement()
        invalid_rows = [
            PendaftaranAsleb(
                nama='Regular Linked', nim='10011', no_hp='08123', program_studi='TI',
                semester=5, matkul=self.course, periode=self.period,
                replacement_process=replacement, candidate_user=self.candidate,
            ),
            PendaftaranAsleb(
                nama='Replacement Unlinked', nim='10012', no_hp='08123',
                program_studi='TI', semester=5, matkul=self.course, periode=self.period,
                jenis=PendaftaranAsleb.JENIS_REPLACEMENT,
            ),
        ]
        for row in invalid_rows:
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    PendaftaranAsleb.objects.bulk_create([row])

    def replacement_registration_values(self, replacement, **overrides):
        values = {
            'nama': 'Candidate', 'nim': '10013', 'no_hp': '08123',
            'program_studi': 'TI', 'semester': 5, 'matkul': self.course,
            'periode': self.period, 'jenis': PendaftaranAsleb.JENIS_REPLACEMENT,
            'replacement_process': replacement, 'candidate_user': self.candidate,
        }
        values.update(overrides)
        return values

    def test_plain_live_replacement_registration_full_clean_derives_guard(self):
        replacement = self.create_replacement()
        registration = PendaftaranAsleb(
            **self.replacement_registration_values(replacement)
        )
        registration.full_clean()
        self.assertEqual(registration.live_candidate_user_id, self.candidate.pk)

    def test_plain_regular_registration_full_clean_remains_compatible(self):
        registration = PendaftaranAsleb(
            nama='Regular Plain', nim='10014', no_hp='08123', program_studi='TI',
            semester=5, matkul=self.course, periode=self.period,
        )
        registration.full_clean()
        self.assertIsNone(registration.live_candidate_user_id)

    def test_two_live_replacement_registrations_are_rejected(self):
        replacement = self.create_replacement()
        values = self.replacement_registration_values(replacement)
        PendaftaranAsleb.objects.create(**values)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendaftaranAsleb.objects.create(**values)

    def test_rejected_history_allows_new_live_reapplication(self):
        replacement = self.create_replacement()
        values = self.replacement_registration_values(replacement)
        historical = PendaftaranAsleb.objects.create(**values, status='ditolak')
        current = PendaftaranAsleb.objects.create(**values)
        self.assertIsNone(historical.live_candidate_user_id)
        self.assertEqual(current.live_candidate_user_id, self.candidate.pk)

    def test_partial_status_transition_releases_and_restores_live_guard(self):
        replacement = self.create_replacement()
        registration = PendaftaranAsleb.objects.create(
            **self.replacement_registration_values(replacement)
        )
        self.assertEqual(registration.live_candidate_user_id, self.candidate.pk)

        registration.status = 'ditolak'
        fields = {'status'}
        registration.save(update_fields=fields)
        self.assertEqual(fields, {'status'})
        registration.refresh_from_db()
        self.assertIsNone(registration.live_candidate_user_id)

        registration.status = 'diajukan'
        fields = ('status',)
        registration.save(update_fields=fields)
        self.assertEqual(fields, ('status',))
        registration.refresh_from_db()
        self.assertEqual(registration.live_candidate_user_id, self.candidate.pk)

    def test_partial_candidate_attname_transition_updates_live_guard(self):
        replacement = self.create_replacement()
        registration = PendaftaranAsleb.objects.create(
            **self.replacement_registration_values(replacement)
        )
        other_candidate = self.create_user('mahasiswa', '90006')
        registration.candidate_user_id = other_candidate.pk
        fields = ['candidate_user_id']
        registration.save(update_fields=fields)
        self.assertEqual(fields, ['candidate_user_id'])
        registration.refresh_from_db()
        self.assertEqual(registration.live_candidate_user_id, other_candidate.pk)

    def test_bulk_create_cannot_bypass_live_registration_guard(self):
        replacement = self.create_replacement()
        row = PendaftaranAsleb(**self.replacement_registration_values(replacement))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendaftaranAsleb.objects.bulk_create([row])

    def test_outgoing_assignment_can_own_only_one_replacement(self):
        self.create_replacement()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_replacement()

    def test_only_one_live_offer_exists_per_replacement(self):
        replacement = self.create_replacement()
        self.create_offer(replacement, status=AslabOffer.STATUS_WAITING)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_offer(replacement, self.create_user('mahasiswa', '90003'))

    def test_inactive_offer_releases_live_guard(self):
        replacement = self.create_replacement()
        offer = self.create_offer(replacement)
        offer.status = AslabOffer.STATUS_DECLINED
        fields = {'status'}
        offer.save(update_fields=fields)
        self.assertEqual(fields, {'status'})
        offer.refresh_from_db()
        self.assertIsNone(offer.live_replacement_id)
        self.create_offer(replacement, self.create_user('mahasiswa', '90004'))

    def test_partial_replacement_and_status_changes_sync_live_guard(self):
        first = self.create_replacement()
        second_slot = AslabSlot.objects.create(periode=self.period, matkul=self.course, nomor=2)
        second_asleb = Asleb.objects.create(
            nama='Second', nim='99002', no_hp='08123', program_studi='TI',
            semester=5, tanggal_bergabung=self.period.mulai,
        )
        second_assignment = AslabAssignment.objects.create(
            slot=second_slot, asleb=second_asleb, mulai_pada=self.period.mulai,
            status=AslabAssignment.STATUS_ACTIVE,
        )
        second = self.create_replacement(slot=second_slot, outgoing_assignment=second_assignment)
        offer = self.create_offer(first)
        fields = ['replacement_id']
        offer.replacement_id = second.pk
        offer.save(update_fields=fields)
        self.assertEqual(fields, ['replacement_id'])
        offer.refresh_from_db()
        self.assertEqual(offer.live_replacement_id, second.pk)

    def test_bulk_create_cannot_bypass_live_offer_guard(self):
        replacement = self.create_replacement()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AslabOffer.objects.bulk_create([
                    AslabOffer(
                        replacement=replacement, candidate=self.candidate,
                        deadline=timezone.now() + timedelta(days=3),
                    ),
                ])

    def test_offer_deadline_is_required_at_model_and_database_layers(self):
        replacement = self.create_replacement()
        offer = AslabOffer(
            replacement=replacement,
            live_replacement=replacement,
            candidate=self.candidate,
        )
        with self.assertRaises(ValidationError):
            offer.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AslabOffer.objects.bulk_create([offer])

    def test_offer_has_specific_notes_fields(self):
        self.assertIsNotNone(AslabOffer._meta.get_field('verification_notes'))
        self.assertIsNotNone(AslabOffer._meta.get_field('decline_reason'))
        with self.assertRaises(FieldDoesNotExist):
            AslabOffer._meta.get_field('notes')

    def test_plain_live_offer_full_clean_derives_guard(self):
        replacement = self.create_replacement()
        offer = AslabOffer(
            replacement=replacement,
            candidate=self.candidate,
            deadline=timezone.now() + timedelta(days=3),
        )
        offer.full_clean()
        self.assertEqual(offer.live_replacement_id, replacement.pk)

    def test_offer_registration_must_match_kind_process_and_candidate(self):
        replacement = self.create_replacement()
        valid = PendaftaranAsleb.objects.create(
            **self.replacement_registration_values(replacement)
        )
        regular = PendaftaranAsleb.objects.create(
            nama='Regular Offer', nim='10015', no_hp='08123', program_studi='TI',
            semester=5, matkul=self.course, periode=self.period,
        )
        other_candidate = self.create_user('mahasiswa', '90007')
        wrong_candidate = PendaftaranAsleb.objects.create(
            **self.replacement_registration_values(
                replacement, candidate_user=other_candidate, nim='10016',
            )
        )
        other_slot = AslabSlot.objects.create(
            periode=self.period, matkul=self.course, nomor=2,
        )
        other_asleb = Asleb.objects.create(
            nama='Other Outgoing', nim='99004', no_hp='08123', program_studi='TI',
            semester=5, tanggal_bergabung=self.period.mulai,
        )
        other_assignment = AslabAssignment.objects.create(
            slot=other_slot, asleb=other_asleb, mulai_pada=self.period.mulai,
            status=AslabAssignment.STATUS_ACTIVE,
        )
        other_replacement = self.create_replacement(
            slot=other_slot, outgoing_assignment=other_assignment,
        )
        wrong_process = PendaftaranAsleb.objects.create(
            **self.replacement_registration_values(
                other_replacement, nim='10017',
            )
        )

        for registration in (regular, wrong_candidate, wrong_process):
            offer = AslabOffer(
                replacement=replacement, candidate=self.candidate,
                registration=registration,
                deadline=timezone.now() + timedelta(days=3),
            )
            with self.assertRaises(ValidationError):
                offer.full_clean()

        offer = AslabOffer(
            replacement=replacement, candidate=self.candidate,
            registration=valid,
            deadline=timezone.now() + timedelta(days=3),
        )
        offer.full_clean()

    def test_replacement_dates_must_share_month_and_transfer_first_day(self):
        for transfer_month in (date(2026, 8, 2), date(2026, 9, 1)):
            replacement = AslabReplacement(
                slot=self.slot, outgoing_assignment=self.assignment,
                effective_date=date(2026, 8, 15), transfer_month=transfer_month,
                created_by=self.creator,
            )
            with self.assertRaises(ValidationError):
                replacement.full_clean()

    def test_opening_close_must_follow_open(self):
        replacement = self.create_replacement()
        now = timezone.now()
        opening = LimitedReplacementOpening(
            replacement=replacement, opens_at=now, closes_at=now - timedelta(seconds=1),
        )
        with self.assertRaises(ValidationError):
            opening.full_clean()

    def test_replacement_slot_must_match_outgoing_assignment(self):
        other_slot = AslabSlot.objects.create(
            periode=self.period, matkul=self.course, nomor=2,
        )
        replacement = AslabReplacement(
            slot=other_slot, outgoing_assignment=self.assignment,
            effective_date=date(2026, 8, 15), transfer_month=date(2026, 8, 1),
            created_by=self.creator,
        )
        with self.assertRaises(ValidationError):
            replacement.full_clean()

    def test_incoming_assignment_must_match_slot_and_replace_outgoing(self):
        incoming_asleb = Asleb.objects.create(
            nama='Incoming', nim='99003', no_hp='08123', program_studi='TI',
            semester=5, tanggal_bergabung=self.period.mulai,
        )
        other_slot = AslabSlot.objects.create(
            periode=self.period, matkul=self.course, nomor=2,
        )
        wrong_slot = AslabAssignment.objects.create(
            slot=other_slot, asleb=incoming_asleb, mulai_pada=date(2026, 8, 15),
            status=AslabAssignment.STATUS_PENDING, menggantikan=self.assignment,
        )
        replacement = AslabReplacement(
            slot=self.slot, outgoing_assignment=self.assignment,
            incoming_assignment=wrong_slot, effective_date=date(2026, 8, 15),
            transfer_month=date(2026, 8, 1), created_by=self.creator,
        )
        with self.assertRaises(ValidationError):
            replacement.full_clean()

        wrong_slot.delete()
        wrong_lineage = AslabAssignment.objects.create(
            slot=self.slot, asleb=incoming_asleb, mulai_pada=date(2026, 8, 15),
            status=AslabAssignment.STATUS_PENDING,
        )
        replacement.incoming_assignment = wrong_lineage
        with self.assertRaises(ValidationError):
            replacement.full_clean()

    def test_workflow_admins_disallow_changes(self):
        for admin_class, model in (
            (AslabReplacementAdmin, AslabReplacement),
            (AslabOfferAdmin, AslabOffer),
            (LimitedReplacementOpeningAdmin, LimitedReplacementOpening),
            (AslabReplacementAuditAdmin, AslabReplacementAudit),
        ):
            model_admin = admin_class(model, admin.site)
            self.assertFalse(model_admin.has_change_permission(None, None))

    def test_nested_workflow_admin_relations_are_preloaded(self):
        for admin_class in (
            AslabOfferAdmin,
            LimitedReplacementOpeningAdmin,
            AslabReplacementAuditAdmin,
        ):
            self.assertIn(
                'replacement__outgoing_assignment__asleb',
                admin_class.list_select_related,
            )
            self.assertIn(
                'replacement__outgoing_assignment__slot',
                admin_class.list_select_related,
            )
            self.assertIn(
                'replacement__outgoing_assignment__slot__periode',
                admin_class.list_select_related,
            )
            self.assertIn(
                'replacement__outgoing_assignment__slot__matkul',
                admin_class.list_select_related,
            )

    def test_protected_and_set_null_relations(self):
        actor = self.create_user('laboran', '90005')
        replacement = self.create_replacement(activated_by=actor)
        registration = PendaftaranAsleb.objects.create(
            nama='Candidate', nim='10002', no_hp='08123', program_studi='TI',
            semester=5, matkul=self.course, periode=self.period,
            jenis=PendaftaranAsleb.JENIS_REPLACEMENT,
            replacement_process=replacement, candidate_user=self.candidate,
        )
        offer = self.create_offer(
            replacement, registration=registration, verified_by=actor,
            status=AslabOffer.STATUS_VERIFIED,
        )
        audit = AslabReplacementAudit.objects.create(
            replacement=replacement, actor=actor, action='created',
            previous_state='', new_state=replacement.status,
        )
        with self.assertRaises(ProtectedError):
            replacement.delete()
        registration.delete()
        actor.delete()
        offer.refresh_from_db()
        replacement.refresh_from_db()
        audit.refresh_from_db()
        self.assertIsNone(offer.registration_id)
        self.assertIsNone(offer.verified_by_id)
        self.assertIsNone(replacement.activated_by_id)
        self.assertIsNone(audit.actor_id)


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
        self.historical_apps = MigrationExecutor(connection).loader.project_state(
            [('pendaftaran_asleb', '0016_aslab_assignment_foundation')]
        ).apps
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
            self.migration.backfill_aslab_assignments(
                self.historical_apps,
                schema_editor,
            )

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

    def test_single_registration_with_conflicting_legacy_course_is_not_assigned(self):
        self.create_registration('10010')
        self.create_active_asleb('10010', 'Conflicting exact course label')

        self.run_backfill()

        self.assertFalse(AslabAssignment.objects.exists())
        self.assertFalse(AslabSlot.objects.exists())

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


class AslabBackfillDatabaseAliasTests(SimpleTestCase):
    def test_backfill_uses_schema_editor_alias_for_all_database_paths(self):
        migration = import_module(
            'apps.pendaftaran_asleb.migrations.0017_backfill_aslab_assignments'
        )
        course = SimpleNamespace(
            pk=31,
            nama='Mata Kuliah Alias',
            dosen='Dosen Alias',
            kelas='TIF-01',
        )
        period = SimpleNamespace(mulai=date(2026, 7, 1))
        asleb = SimpleNamespace(
            pk=11,
            nim='ALIAS01',
            matkul='',
            periode_aktif_id=21,
            periode_aktif=period,
        )
        registration = SimpleNamespace(pk=41, matkul_id=course.pk, matkul=course)
        slot = SimpleNamespace(pk=51, status='vacant', save=Mock())

        def historical_model(aliased_manager):
            direct_manager = Mock()
            direct_manager.filter.side_effect = AssertionError(
                'historical manager must be bound with using(alias)'
            )
            direct_manager.using.return_value = aliased_manager
            return type('HistoricalModel', (), {'objects': direct_manager})

        asleb_manager = Mock()
        asleb_queryset = asleb_manager.filter.return_value
        asleb_queryset.select_related.return_value.order_by.return_value.iterator.return_value = [
            asleb
        ]
        registration_manager = Mock()
        registration_queryset = registration_manager.filter.return_value
        registration_queryset.select_related.return_value.order_by.return_value = [
            registration
        ]
        assignment_manager = Mock()
        assignment_manager.filter.side_effect = [
            Mock(exists=Mock(return_value=False)),
            Mock(values_list=Mock(return_value=[])),
        ]
        slot_manager = Mock()
        slot_manager.filter.return_value.values_list.return_value = []
        slot_manager.get_or_create.return_value = (slot, False)

        model_map = {
            ('asleb', 'Asleb'): historical_model(asleb_manager),
            ('pendaftaran_asleb', 'PendaftaranAsleb'): historical_model(
                registration_manager
            ),
            ('pendaftaran_asleb', 'AslabSlot'): historical_model(slot_manager),
            ('pendaftaran_asleb', 'AslabAssignment'): historical_model(
                assignment_manager
            ),
        }
        historical_apps = Mock()
        historical_apps.get_model.side_effect = lambda *key: model_map[key]
        schema_editor = SimpleNamespace(connection=SimpleNamespace(alias='archive'))

        migration.backfill_aslab_assignments(historical_apps, schema_editor)

        for model in model_map.values():
            model.objects.using.assert_called_once_with('archive')
        slot.save.assert_called_once_with(
            using='archive',
            update_fields=['status', 'diperbarui_pada'],
        )
        assignment_manager.create.assert_called_once()


class AuditAslabSlotsCommandTests(AslabBackfillTests):
    def test_audit_reports_single_candidate_course_mismatch_and_strict_fails(self):
        self.create_registration('20009')
        self.create_active_asleb('20009', 'Conflicting exact course label')
        output = StringIO()

        with self.assertRaises(CommandError):
            call_command('audit_aslab_slots', '--strict', stdout=output)

        self.assertIn('COURSE_MISMATCH: 20009', output.getvalue())

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

    def test_strict_fails_for_inconsistent_occupancy(self):
        registrations = [
            self.create_registration('20010'),
            self.create_registration('20011'),
        ]
        self.create_active_asleb('20010')
        self.run_backfill()
        AslabAssignment.objects.update(source_pendaftaran=registrations[1])

        with self.assertRaises(CommandError):
            call_command('audit_aslab_slots', '--strict', stdout=StringIO())

    def test_strict_gate_fails_for_duplicate_occupancy_category(self):
        command_module = import_module(
            'apps.pendaftaran_asleb.management.commands.audit_aslab_slots'
        )
        categories = defaultdict(list, {
            'DUPLICATE_OCCUPANCY': ['slot 1 assignments [1, 2]'],
        })

        with self.assertRaises(CommandError):
            command_module.Command().raise_for_strict_issues(categories)
