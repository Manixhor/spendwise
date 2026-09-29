"""Browser-free checks for the office page's in-place update behaviour.

These assert the contract the JavaScript relies on: the page must ship the
hooks the script needs, and recording an entry must return everything needed
to redraw the page without a reload.
"""

import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import OfficeEntry


class OfficeLiveUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="live@example.com", email="live@example.com", password="secret123"
        )
        self.client.force_login(self.user)

    def _add(self, **payload):
        return self.client.post(
            reverse("api_office_add_entry"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_add_entry_response_carries_everything_the_ui_needs(self):
        response = self._add(direction="came", name="Ravi", amount="250.50")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Redrawing the page in place depends on all of these.
        for key in (
            "id", "created_at", "entry_date",
            "total", "opening", "came_total", "taken_total",
        ):
            self.assertIn(key, data)
        self.assertEqual(data["total"], "250.50")
        self.assertEqual(data["came_total"], "250.50")

    def test_page_ships_the_hooks_the_live_update_needs(self):
        OfficeEntry.objects.create(
            user=self.user, direction="came", amount="10", name="Ravi"
        )
        html = self.client.get(reverse("office")).content.decode()

        # Toast container plus its text/icon targets.
        self.assertIn('id="officeToast"', html)
        self.assertIn('id="officeToastText"', html)
        self.assertIn('id="officeToastIcon"', html)

        # The page size has to be readable by the script so the on-screen
        # list stays the same length as the server-rendered page.
        self.assertIn("const PAGE_SIZE =", html)
        self.assertIn('data-total="1"', html)

        # A row template to clone, and the in-place update path.
        self.assertIn("prependHistoryRow", html)
        self.assertIn("resetDateField", html)
        # No reload on save.
        self.assertNotIn(
            "window.location.assign", html.split("function bindEntryForm")[1][:2000]
        )

    def test_recording_updates_totals_without_a_reload(self):
        self._add(direction="came", name="Ravi", amount="100")
        second = self._add(direction="taken", name="Anita", amount="30")

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["total"], "70.00")

        # Server state agrees with what the client would have drawn.
        page = self.client.get(reverse("office"))
        self.assertEqual(page.context["office_total"], Decimal("70.00"))
        self.assertEqual(OfficeEntry.objects.filter(user=self.user).count(), 2)
