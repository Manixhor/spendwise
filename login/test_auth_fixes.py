from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import UserProfile


class AuthFixTests(TestCase):
    def test_failed_resend_preserves_previous_code(self):
        user = User.objects.create_user(
            username="pending@example.com", email="pending@example.com",
            password="StrongPass123!", is_active=False,
        )
        profile = UserProfile.objects.get(user=user)
        profile.email_verification_code = "1234"
        profile.email_verification_sent_at = timezone.now()
        profile.save(update_fields=["email_verification_code", "email_verification_sent_at"])
        session = self.client.session
        session["pending_signup_user_id"] = user.id
        session.save()

        with patch("login.views._send_signup_otp_email", side_effect=OSError("mail unavailable")):
            response = self.client.post(reverse("signup_verify"), {"action": "resend"})

        self.assertContains(response, "could not resend")
        profile.refresh_from_db()
        self.assertEqual(profile.email_verification_code, "1234")
        self.assertIsNotNone(profile.email_verification_sent_at)

    def test_signup_email_error_shows_first_step(self):
        response = self.client.post(reverse("signup"), {
            "name": "", "email": "invalid", "password": "bad", "confirm_password": "bad",
        })
        self.assertContains(response, 'data-step="1"')

    def test_office_navigation_icon_is_hidden(self):
        user = User.objects.create_user(username="test@example.com", password="StrongPass123!")
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, 'aria-label="Office"')
