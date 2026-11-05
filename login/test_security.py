import io
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import UserProfile
from .security import clean_avatar
from .views import _issue_password_reset_otp, _issue_signup_otp


@override_settings(SECURE_SSL_REDIRECT=False)
class SecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='secure@example.com', email='secure@example.com', password='StrongPass123!')
        self.profile = UserProfile.objects.get(user=self.user)

    def reset_session(self, client=None):
        client = client or self.client
        session = client.session
        session['password_reset_user_id'] = self.user.pk
        session['password_reset_email'] = self.user.email
        session.save()

    def test_issued_codes_are_hashed(self):
        for issue, field in [(_issue_signup_otp, 'email_verification_code'), (_issue_password_reset_otp, 'password_reset_code')]:
            code = issue(self.profile)
            self.profile.refresh_from_db()
            self.assertEqual(len(code), 4)
            self.assertNotEqual(getattr(self.profile, field), code)
            self.assertTrue(check_password(code, getattr(self.profile, field)))

    def test_verify_limit_survives_new_session_and_resend(self):
        _issue_password_reset_otp(self.profile)
        self.reset_session()
        for _ in range(5):
            self.assertEqual(self.client.post(reverse('forgot_password_verify'), {'otp': 'bad'}).status_code, 200)
        other = Client(REMOTE_ADDR='192.0.2.5')
        self.reset_session(other)
        self.assertEqual(other.post(reverse('forgot_password_verify'), {'otp': 'bad'}).status_code, 429)
        with patch('login.views._send_password_reset_otp_email'):
            self.client.post(reverse('forgot_password_verify'), {'action': 'resend'})
        self.assertEqual(self.client.post(reverse('forgot_password_verify'), {'otp': 'bad'}).status_code, 429)

    def test_send_limit_and_unknown_account_have_same_response(self):
        with patch('login.views._send_password_reset_otp_email'):
            known = self.client.post(reverse('forgot_password'), {'email': self.user.email})
            unknown = Client().post(reverse('forgot_password'), {'email': 'missing@example.com'})
            self.assertEqual(known.status_code, unknown.status_code)
            self.assertEqual(known.url, unknown.url)
            self.client.post(reverse('forgot_password'), {'email': self.user.email})
            self.client.post(reverse('forgot_password'), {'email': self.user.email})
            response = self.client.post(reverse('forgot_password'), {'email': self.user.email})
            self.assertEqual(response.status_code, 429)

    def test_valid_reset_consumes_code_and_authorization_expires(self):
        code = _issue_password_reset_otp(self.profile)
        self.reset_session()
        response = self.client.post(reverse('forgot_password_verify'), {'otp': code})
        self.assertEqual(response.url, reverse('forgot_password_reset'))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.password_reset_code, '')
        session = self.client.session
        session['password_reset_verified_at'] = (timezone.now() - timedelta(minutes=11)).timestamp()
        session.save()
        self.assertEqual(self.client.get(reverse('forgot_password_reset')).url, reverse('forgot_password'))

    def test_invalid_and_oversized_uploads_rejected(self):
        for content in [b'<script>bad</script>', b'x' * (2 * 1024 * 1024 + 1)]:
            with self.assertRaises(ValidationError):
                clean_avatar(SimpleUploadedFile('avatar.png', content, content_type='image/png'))

    def test_avatar_is_reencoded_and_randomly_named(self):
        data = io.BytesIO()
        Image.new('RGB', (4, 4)).save(data, format='PNG')
        cleaned = clean_avatar(SimpleUploadedFile('evil.html', data.getvalue() + b'<script>bad</script>'))
        self.assertTrue(cleaned.name.endswith('.jpg'))
        self.assertNotIn(b'<script>', cleaned.read())

    def test_invalid_avatar_does_not_update_profile(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('profile'), {'first_name': 'Changed', 'avatar': SimpleUploadedFile('x.png', b'bad')})
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.first_name, 'Changed')

    def test_api_failure_does_not_disclose_exception(self):
        self.client.force_login(self.user)
        with patch('login.views._dashboard_stats', side_effect=RuntimeError('private-db-host: leaked credential')), self.assertLogs('login.views', level='ERROR'):
            response = self.client.post(reverse('api_set_salary'), data='{"salary": 1000}', content_type='application/json')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {'error': 'Something went wrong. Please try again.'})
        self.assertNotContains(response, 'private-db-host', status_code=500)

    def test_media_not_served_by_django_in_production(self):
        from importlib import reload
        import config.urls
        from django.urls import clear_url_caches, resolve, Resolver404
        try:
            with override_settings(DEBUG=False, SERVE_MEDIA_WITH_DJANGO=False):
                reload(config.urls)
                clear_url_caches()
                with self.assertRaises(Resolver404):
                    resolve('/media/avatars/test.jpg')
        finally:
            reload(config.urls)
            clear_url_caches()
