from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from .models import Transaction, UserProfile


@override_settings(SECURE_SSL_REDIRECT=False)
class AccountDeletionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test@example.com", email="test@example.com", password="StrongPass123!")
        UserProfile.objects.get_or_create(user=self.user)
        Transaction.objects.create(user=self.user, title="Coffee", amount=100, date="2026-11-01", txn_type="expense", category="food")

    def test_public_deletion_page_and_privacy_policy(self):
        self.assertEqual(self.client.get(reverse("delete_account")).status_code, 200)
        self.assertContains(self.client.get(reverse("privacy_policy")), "Delete account")

    def test_deletion_requires_password_and_confirmation(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("delete_account"), {"password": "wrong", "confirmation": "DELETE"})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_deletion_removes_account_records_and_session(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("delete_account"), {"password": "StrongPass123!", "confirmation": "DELETE"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Transaction.objects.filter(user_id=self.user.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_account_without_password_can_request_deletion(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        self.client.force_login(self.user)
        response = self.client.post(reverse("delete_account"), {"email": self.user.email, "confirmation": "DELETE"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
