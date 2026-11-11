import json
import re

from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class SearchVisibilityTests(TestCase):
    def test_sitemap_lists_only_public_search_pages(self):
        response = self.client.get(reverse("sitemap"), HTTP_HOST="testserver", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/xml"))
        content = response.content.decode()
        for path in ("/", "/privacy/", "/download/android/"):
            self.assertIn(f"https://testserver{path}</loc>", content)
        self.assertNotIn("/dashboard/", content)
        self.assertNotIn("/login/", content)

    def test_robots_points_to_sitemap(self):
        response = self.client.get(reverse("robots_txt"), secure=True)
        self.assertContains(response, "Sitemap: https://testserver/sitemap.xml")

    def test_public_pages_have_canonical_and_description(self):
        for name in ("onboarding", "privacy_policy", "android_download"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name), secure=True)
                self.assertContains(response, f'<link rel="canonical" href="https://testserver{reverse(name)}"')
                self.assertContains(response, '<meta name="description"')
                self.assertNotIn("X-Robots-Tag", response)

    def test_private_pages_are_not_indexable(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_homepage_identifies_spendwise_as_site_name(self):
        response = self.client.get(reverse("onboarding"), secure=True)
        self.assertContains(response, "<h1 class=\"hero-title\">SpendWise:")
        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', response.content.decode())
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertEqual(data["@type"], "WebSite")
        self.assertEqual(data["name"], "SpendWise")
        self.assertEqual(data["url"], "https://testserver/")
