from unittest.mock import patch
from django.contrib.auth.hashers import make_password

from django.contrib.auth.models import User
from django.test import TestCase
from django.test import Client
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
        profile.email_verification_code = make_password("1234")
        previous_code = profile.email_verification_code
        profile.email_verification_sent_at = timezone.now()
        profile.save(update_fields=["email_verification_code", "email_verification_sent_at"])
        session = self.client.session
        session["pending_signup_user_id"] = user.id
        session.save()

        with patch("login.views._send_signup_otp_email", side_effect=OSError("mail unavailable")):
            response = self.client.post(reverse("signup_verify"), {"action": "resend"})

        self.assertContains(response, "could not resend")
        profile.refresh_from_db()
        self.assertEqual(profile.email_verification_code, previous_code)
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

    def test_android_webview_login_keeps_session(self):
        email = 'android@example.com'
        user = User.objects.create_user(username=email, email=email, password='StrongPass123!')
        profile = user.profile
        profile.email_is_verified = True
        profile.save(update_fields=['email_is_verified'])
        client = Client(enforce_csrf_checks=True, HTTP_USER_AGENT='Mozilla/5.0 Android; wv) SpendwiseAndroid/4')
        login_page = client.get(reverse('login'))
        self.assertEqual(login_page.status_code, 200)
        self.assertNotContains(login_page, 'id="liSubmitBtn" disabled')
        response = client.post(reverse('login'), {
            'email': email, 'password': 'StrongPass123!',
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(client.get(reverse('dashboard')).status_code, 200)

    def test_correct_login_after_several_failed_attempts(self):
        email = 'retry@example.com'
        user = User.objects.create_user(username=email, email=email, password='StrongPass123!')
        profile = user.profile
        profile.email_is_verified = True
        profile.save(update_fields=['email_is_verified'])
        for _ in range(4):
            response = self.client.post(reverse('login'), {'email': email, 'password': 'wrong'})
            self.assertContains(response, 'Invalid email or password.')
        self.assertRedirects(self.client.post(reverse('login'), {
            'email': email, 'password': 'StrongPass123!',
        }), reverse('dashboard'))

    def test_repeated_wrong_password_is_limited(self):
        email = 'limited@example.com'
        for _ in range(10):
            self.client.post(reverse('login'), {'email': email, 'password': 'wrong'})
        response = self.client.post(reverse('login'), {'email': email, 'password': 'wrong'})
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, 'Too many unsuccessful sign-in attempts', status_code=429)

    @patch('login.views._send_new_signup_otp')
    def test_verified_account_logs_in_without_email_otp(self, send_otp):
        email = 'legacy@example.com'
        user = User.objects.create_user(username=email, email=email, password='StrongPass123!', is_active=True)
        profile = user.profile
        profile.email_is_verified = True
        profile.save(update_fields=['email_is_verified'])
        response = self.client.post(reverse('login'), {
            'email': email, 'password': 'StrongPass123!',
        })
        self.assertRedirects(response, reverse('dashboard'))
        send_otp.assert_not_called()
