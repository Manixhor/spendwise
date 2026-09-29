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

        # The list is re-rendered from the server fragment rather than
        # rebuilt in the browser.
        self.assertIn("renderHistory", html)
        self.assertIn("officeHistorySection", html)
        self.assertIn("resetDateField", html)
        # No reload on the happy path, and no client-side row builder.
        self.assertNotIn(
            "window.location.assign", html.split("function bindEntryForm")[1][:2000]
        )
        self.assertNotIn("buildHistoryRow", html)
        self.assertNotIn("HISTORY_ROW_TEMPLATE", html)

    def test_first_entry_appears_in_the_fragment_without_a_reload(self):
        """The bug this guards: an empty list has no row to clone, so the
        first entry was saved but rendered as a blank row until a refresh.
        """
        empty = self.client.get(reverse("office_history_fragment")).content.decode()
        self.assertIn("No entries yet", empty)
        self.assertNotIn("office-history-row", empty)

        self._add(direction="taken", name="Anita", amount="30")

        after = self.client.get(reverse("office_history_fragment")).content.decode()
        self.assertIn("office-history-row", after)
        self.assertIn("Anita", after)
        self.assertIn("Paid", after)
        self.assertIn("1 entry", after)  # caption, not "entries"
        self.assertNotIn("No entries yet", after)

    def test_fragment_respects_search_and_pagination(self):
        for i in range(12):
            OfficeEntry.objects.create(
                user=self.user, direction="came", amount="10", name=f"Person{i:02d}"
            )
        # Page 1 holds eight rows; the remaining rows are on page 2.
        page_one = self.client.get(
            reverse("office_history_fragment"), {"page": 1}
        ).content.decode()
        self.assertEqual(page_one.count("office-history-row"), 8)
        self.assertIn("Page 1 of 2", page_one)
        page_two = self.client.get(
            reverse("office_history_fragment"), {"page": 2}
        ).content.decode()
        self.assertEqual(page_two.count("office-history-row"), 4)
        self.assertIn("Page 2 of 2", page_two)

        # A search filter is carried through the fragment, not ignored.
        filtered = self.client.get(
            reverse("office_history_fragment"), {"q": "Person03"}
        ).content.decode()
        self.assertIn("Search results", filtered)
        self.assertEqual(filtered.count("office-history-row"), 1)

    def test_fragment_is_scoped_to_the_signed_in_user(self):
        OfficeEntry.objects.create(
            user=self.user, direction="came", amount="10", name="Mine"
        )
        other = User.objects.create_user(
            username="other@example.com", email="other@example.com", password="secret123"
        )
        OfficeEntry.objects.create(
            user=other, direction="came", amount="999", name="Theirs"
        )
        html = self.client.get(reverse("office_history_fragment")).content.decode()
        self.assertIn("Mine", html)
        self.assertNotIn("Theirs", html)

    def test_starting_balance_saves_only_when_the_user_saves_it(self):
        """Typing previews the new figure but must not persist it. The
        balance changes only via Save Balance or Enter."""
        html = self.client.get(reverse("office")).content.decode()
        self.assertIn("previewOpening", html)
        # Nothing reaches the server on a timer or on blur.
        self.assertNotIn("scheduleOpeningSave", html)
        self.assertNotIn("openingSaveTimer", html)
        self.assertIn("openingInput.addEventListener('input', previewOpening)", html)
        # The only two ways to persist it.
        self.assertIn("balanceSave.addEventListener('click'", html)
        self.assertIn("saveBalance();", html)
        # No confirmation modal in the way.
        self.assertNotIn("officeBalanceDialog", html)
        self.assertNotIn("balanceConfirm", html)

    def test_setting_the_balance_by_api_still_moves_the_total(self):
        response = self._add(direction="came", name="Ravi", amount="500")
        self.assertEqual(response.status_code, 200)

        balance = self.client.post(
            reverse("api_office_set_balance"),
            data=json.dumps({"amount": "100000"}),
            content_type="application/json",
        )
        self.assertEqual(balance.status_code, 200)
        data = balance.json()
        self.assertEqual(data["opening"], "100000.00")
        self.assertEqual(data["total"], "100500.00")

        # The page the user is looking at agrees.
        page = self.client.get(reverse("office"))
        self.assertEqual(page.context["office_opening"], Decimal("100000.00"))
        self.assertEqual(page.context["office_total"], Decimal("100500.00"))

    def test_direction_filter_narrows_the_list_and_marks_the_button(self):
        for i in range(4):
            OfficeEntry.objects.create(
                user=self.user, direction="came", amount="10", name=f"In{i}"
            )
        for i in range(6):
            OfficeEntry.objects.create(
                user=self.user, direction="taken", amount="10", name=f"Out{i}"
            )

        def fragment(**params):
            return self.client.get(reverse("office_history_fragment"), params).content.decode()

        received = fragment(dir="came")
        self.assertIn("In3", received)
        self.assertNotIn("Out0", received)
        self.assertIn('data-office-filter="came" class="is-active" aria-pressed="true"', received)
        self.assertIn(
            'data-office-filter="taken" aria-pressed="false"', received
        )

        paid = fragment(dir="taken")
        self.assertIn("Out5", paid)
        self.assertNotIn("In0", paid)

        # Unknown values fall back to everything rather than an empty list.
        every = fragment(dir="nonsense")
        self.assertEqual(every.count("office-history-row"), 8)
        self.assertIn("Out0", every)
        older = fragment(dir="nonsense", page=2)
        self.assertIn("In0", older)
        self.assertEqual(older.count("office-history-row"), 2)

    def test_search_and_direction_filter_combine(self):
        OfficeEntry.objects.create(
            user=self.user, direction="came", amount="10", name="Ravi"
        )
        OfficeEntry.objects.create(
            user=self.user, direction="taken", amount="10", name="Ravi"
        )
        OfficeEntry.objects.create(
            user=self.user, direction="came", amount="10", name="Anita"
        )

        html = self.client.get(
            reverse("office_history_fragment"), {"q": "Ravi", "dir": "came"}
        ).content.decode()
        self.assertEqual(html.count("office-history-row"), 1)
        self.assertIn("Received", html)
        # "Paid" is also a filter button label, so check the row data itself.
        self.assertNotIn('data-direction="taken"', html)

    def test_search_shows_the_eight_most_recent_matches(self):
        for i in range(12):
            OfficeEntry.objects.create(
                user=self.user, direction="came", amount="10", name="Match"
            )
        filtered = self.client.get(
            reverse("office_history_fragment"), {"q": "Match"}
        ).content.decode()
        # Search uses the same eight-row page size.
        self.assertEqual(filtered.count("office-history-row"), 8)
        self.assertIn("12 entries", filtered)  # caption reports every match
        self.assertIn("Page 1 of 2", filtered)

    def test_page_searches_in_place(self):
        html = self.client.get(reverse("office")).content.decode()
        # Submitting the form and paging are both intercepted, so neither
        # reloads the document.
        self.assertIn("addEventListener('submit'", html)
        self.assertIn("event.preventDefault()", html)
        # Typing filters as you go, debounced to one request per pause.
        self.assertIn("setTimeout(() => runSearch(typedSearch()), 250)", html)
        # The query is mirrored into the URL so a refresh keeps it.
        self.assertIn("window.history.replaceState", html)
        # The search form is never swapped out, which would eat the caret.
        self.assertNotIn("'.office-search-row',", html)

    def test_recording_updates_totals_without_a_reload(self):
        self._add(direction="came", name="Ravi", amount="100")
        second = self._add(direction="taken", name="Anita", amount="30")

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["total"], "70.00")

        # Server state agrees with what the client would have drawn.
        page = self.client.get(reverse("office"))
        self.assertEqual(page.context["office_total"], Decimal("70.00"))
        self.assertEqual(OfficeEntry.objects.filter(user=self.user).count(), 2)
