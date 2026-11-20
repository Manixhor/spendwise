from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class AndroidReleaseTests(TestCase):
    def test_download_page_has_apk_and_qr(self):
        response = self.client.get(reverse('android_download'))
        self.assertContains(response, 'Download APK')
        self.assertContains(response, reverse('android_apk'))
        self.assertContains(response, 'Spendwise-QR.png')

    def test_signed_in_download_page_keeps_spendwise_navigation(self):
        user = User.objects.create_user('download@example.test', 'download@example.test', 'DemoPass123!')
        self.client.force_login(user)
        response = self.client.get(reverse('android_download'))
        self.assertContains(response, 'class="sidebar"')
        self.assertContains(response, 'aria-label="Dashboard"')
        self.assertContains(response, 'nav-icon active" aria-label="App Download"')

    def test_android_app_hides_website_download_navigation(self):
        user = User.objects.create_user('demo@example.test', 'demo@example.test', 'DemoPass123!')
        self.client.force_login(user)
        web = self.client.get(reverse('dashboard'))
        android = self.client.get(reverse('dashboard'), HTTP_USER_AGENT='Mozilla/5.0 (Linux; Android 16; wv) SpendwiseAndroid/2')
        self.assertContains(web, 'aria-label="App Download"')
        self.assertNotContains(android, 'aria-label="App Download"')
        self.assertContains(android, 'id="swTabSwitcher"')
        self.assertContains(android, 'tab_switcher.js')

    def test_latest_version_points_to_apk(self):
        response = self.client.get(reverse('android_latest_version'))
        self.assertEqual(response.json()['version_code'], 6)
        self.assertEqual(response.json()['download_url'], reverse('android_apk'))

    def test_apk_download_has_android_filename_and_type(self):
        response = self.client.get(reverse('android_apk'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.android.package-archive')
        self.assertIn('filename="Spendwise.apk"', response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        response.close()

    def test_download_page_is_hidden_inside_installed_app(self):
        response = self.client.get(reverse('android_download'), HTTP_USER_AGENT='Mozilla/5.0 (Linux; Android 16; wv)')
        self.assertRedirects(response, reverse('onboarding'))
