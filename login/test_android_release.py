from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class AndroidReleaseTests(TestCase):
    def test_download_page_has_apk_and_qr(self):
        response = self.client.get(reverse('android_download'))
        self.assertContains(response, 'Download APK')
        self.assertContains(response, 'Spendwise-QR.png')

    def test_android_app_hides_website_download_navigation(self):
        user = User.objects.create_user('demo@example.test', 'demo@example.test', 'DemoPass123!')
        self.client.force_login(user)
        web = self.client.get(reverse('dashboard'))
        android = self.client.get(reverse('dashboard'), HTTP_USER_AGENT='Mozilla/5.0 (Linux; Android 16; wv) SpendwiseAndroid/2')
        self.assertContains(web, 'aria-label="App Download"')
        self.assertNotContains(android, 'aria-label="App Download"')

    def test_latest_version_points_to_apk(self):
        response = self.client.get(reverse('android_latest_version'))
        self.assertEqual(response.json()['version_code'], 3)
        self.assertTrue(response.json()['download_url'].endswith('.apk'))

    def test_download_page_is_hidden_inside_installed_app(self):
        response = self.client.get(reverse('android_download'), HTTP_USER_AGENT='Mozilla/5.0 (Linux; Android 16; wv)')
        self.assertRedirects(response, reverse('onboarding'))
