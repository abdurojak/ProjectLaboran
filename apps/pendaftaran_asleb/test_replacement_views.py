from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.asleb.models import Asleb
from apps.pengguna.models import Pengguna

from .models import (
    AslabAssignment,
    AslabOffer,
    AslabReplacement,
    AslabSlot,
    MataKuliahAsleb,
    PeriodeAsleb,
)


class ReplacementViewTests(TestCase):
    def setUp(self):
        self.laboran = self.user('LAB-WEB', 'Laboran', 'laboran')
        self.student = self.user('WEB-01', 'Kandidat', 'mahasiswa')
        self.other = self.user('WEB-02', 'Mahasiswa Lain', 'mahasiswa')
        self.period = PeriodeAsleb.objects.create(
            tahun=2026, semester=2, mulai=date(2026, 7, 1), selesai=date(2026, 12, 31),
            pendaftaran_mulai=date(2026, 7, 1), pendaftaran_selesai=date(2026, 7, 31),
        )
        self.course = MataKuliahAsleb.objects.create(
            kode='WEB01', kode_mk='WEB01', nama='Web Workflow', dosen='Dosen', kelas='A',
        )
        self.slot = AslabSlot.objects.create(
            periode=self.period, matkul=self.course, nomor=1, status=AslabSlot.STATUS_VACANT,
        )
        self.outgoing = Asleb.objects.create(
            nama='Aslab Lama', nim='OLD-WEB', no_hp='081', email='old-web@example.com',
            program_studi='TI', semester=5, status='nonaktif', periode_aktif=self.period,
            tanggal_bergabung=date(2026, 7, 1),
        )
        self.assignment = AslabAssignment.objects.create(
            slot=self.slot, asleb=self.outgoing, mulai_pada=date(2026, 7, 1),
            berakhir_pada=date(2026, 9, 1), status=AslabAssignment.STATUS_RESIGNED,
        )
        self.replacement = AslabReplacement.objects.create(
            slot=self.slot, outgoing_assignment=self.assignment,
            effective_date=date(2026, 9, 1), transfer_month=date(2026, 9, 1),
            created_by=self.laboran,
        )
        self.offer = AslabOffer.objects.create(
            replacement=self.replacement, candidate=self.student,
            deadline=timezone.now() + timedelta(days=3),
        )

    def user(self, nim, name, role):
        return Pengguna.objects.create(
            nama_pengguna=name, nim_nik=nim, email=f'{nim}@example.com', password='secret',
            no_hp='08123', alamat='Jakarta', fakultas='FTI', prodi='TI',
            gender='laki_laki', role=role, is_verified=True,
        )

    def login(self, user):
        session = self.client.session
        session['pengguna_id'] = user.pk
        session.save()

    def test_student_cannot_open_laboran_replacement_dashboard(self):
        self.login(self.student)
        response = self.client.get(reverse('pendaftaran_asleb:replacement_list'))
        self.assertEqual(response.status_code, 302)

    def test_other_candidate_cannot_learn_offer_exists(self):
        self.login(self.other)
        for name in ('replacement_offer_accept', 'replacement_offer_decline', 'replacement_candidate_data'):
            response = self.client.get(reverse(f'pendaftaran_asleb:{name}', args=[self.offer.pk]))
            self.assertEqual(response.status_code, 404)

    def test_candidate_offer_page_shows_consent_boundary(self):
        self.login(self.student)
        response = self.client.get(reverse('pendaftaran_asleb:replacement_offer_accept', args=[self.offer.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Web Workflow')
        self.assertContains(response, 'Bulan pengalihan honor')
        self.assertContains(response, 'Terima tawaran')

    @patch('apps.pendaftaran_asleb.replacement_views.accept_offer')
    def test_accept_is_post_only_and_calls_service(self, service):
        service.return_value = self.offer
        self.login(self.student)
        url = reverse('pendaftaran_asleb:replacement_offer_accept', args=[self.offer.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('pendaftaran_asleb:replacement_candidate_data', args=[self.offer.pk]))
        service.assert_called_once_with(offer_id=self.offer.pk, candidate=self.student)

    @patch('apps.pendaftaran_asleb.replacement_views.end_assignment_for_replacement')
    def test_end_form_previews_boundary_and_delegates(self, service):
        active = AslabAssignment.objects.create(
            slot=AslabSlot.objects.create(
                periode=self.period, matkul=self.course, nomor=2, status=AslabSlot.STATUS_ACTIVE,
            ),
            asleb=self.outgoing, mulai_pada=date(2026, 7, 1), status=AslabAssignment.STATUS_ACTIVE,
        )
        service.return_value = self.replacement
        self.login(self.laboran)
        url = reverse('pendaftaran_asleb:replacement_end', args=[active.pk])
        response = self.client.get(url)
        self.assertContains(response, 'Honor sebelum bulan efektif tetap menjadi hak aslab lama')
        response = self.client.post(url, {
            'reason_type': 'resignation', 'reason': 'Mengundurkan diri',
            'effective_date': '2026-09-01', 'method': 'direct_offer',
        })
        self.assertEqual(response.status_code, 302)
        service.assert_called_once()

    def test_laboran_list_and_detail_render_workflow_state(self):
        self.login(self.laboran)
        response = self.client.get(reverse('pendaftaran_asleb:replacement_list'))
        self.assertContains(response, 'Web Workflow')
        self.assertContains(response, 'Aslab Lama')
        response = self.client.get(reverse('pendaftaran_asleb:replacement_detail', args=[self.replacement.pk]))
        self.assertContains(response, self.replacement.get_status_display())

    def test_state_changing_routes_reject_get(self):
        self.login(self.student)
        decline = self.client.get(reverse('pendaftaran_asleb:replacement_offer_decline', args=[self.offer.pk]))
        self.assertEqual(decline.status_code, 405)

    @patch('apps.pendaftaran_asleb.replacement_views.create_direct_offer')
    def test_laboran_offer_form_delegates_to_service(self, service):
        self.offer.delete()
        self.login(self.laboran)
        deadline = timezone.now() + timedelta(days=2)
        response = self.client.post(
            reverse('pendaftaran_asleb:replacement_offer_create', args=[self.replacement.pk]),
            {'candidate': self.student.pk, 'deadline': deadline.strftime('%Y-%m-%dT%H:%M')},
        )
        self.assertEqual(response.status_code, 302)
        service.assert_called_once()

    @patch('apps.pendaftaran_asleb.replacement_views.decline_offer')
    def test_candidate_decline_delegates_with_reason(self, service):
        self.login(self.student)
        response = self.client.post(
            reverse('pendaftaran_asleb:replacement_offer_decline', args=[self.offer.pk]),
            {'reason': 'Tidak dapat memenuhi jadwal'},
        )
        self.assertEqual(response.status_code, 302)
        service.assert_called_once_with(
            offer_id=self.offer.pk, candidate=self.student,
            reason='Tidak dapat memenuhi jadwal',
        )

    @patch('apps.pendaftaran_asleb.replacement_views.return_offer_for_revision')
    def test_laboran_can_return_submission_for_revision(self, service):
        self.login(self.laboran)
        response = self.client.post(
            reverse('pendaftaran_asleb:replacement_verify', args=[self.offer.pk]),
            {'action': 'revision', 'notes': 'Perbaiki data rekening'},
        )
        self.assertEqual(response.status_code, 302)
        service.assert_called_once_with(
            offer_id=self.offer.pk, actor=self.laboran, notes='Perbaiki data rekening',
        )

    @patch('apps.pendaftaran_asleb.replacement_views.open_limited_registration')
    def test_laboran_opening_form_delegates_filters(self, service):
        self.login(self.laboran)
        opens = timezone.now() + timedelta(hours=1)
        closes = opens + timedelta(days=2)
        response = self.client.post(
            reverse('pendaftaran_asleb:replacement_opening', args=[self.replacement.pk]),
            {
                'action': 'open', 'opens_at': opens.strftime('%Y-%m-%dT%H:%M'),
                'closes_at': closes.strftime('%Y-%m-%dT%H:%M'),
                'program_studi': 'TI', 'cohort': 2023,
                'allowed_candidates': [self.student.pk], 'requirements': 'Siap mengajar',
            },
        )
        self.assertEqual(response.status_code, 302)
        service.assert_called_once()
