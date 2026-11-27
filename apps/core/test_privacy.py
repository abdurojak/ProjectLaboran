from django.test import TestCase
from django.urls import reverse


class PrivacyPolicyTests(TestCase):
    def test_policy_is_public_and_contains_deletion_contact(self):
        response = self.client.get(reverse('privacy_policy'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Permintaan Penghapusan Akun LabHub')
        self.assertContains(response, 'Labtif.fti@trisakti.ac.id')
