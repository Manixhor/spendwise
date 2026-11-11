from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Transaction
from .views import _daily_spending_allowance


class SpendingToolsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="spending-tools")
        self.profile = self.user.profile
        self.client.force_login(self.user)

    def test_user_sets_allowance_after_salary_and_sees_today_progress(self):
        url = reverse("profile")
        response = self.client.post(url, {
            "action": "daily_allowance", "daily_spending_allowance": "500.25",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.profile.daily_spending_allowance)

        self.profile.salary = Decimal("10000")
        self.profile.save(update_fields=["salary"])
        response = self.client.post(url, {
            "action": "daily_allowance", "daily_spending_allowance": "500.25",
        })
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.daily_spending_allowance, Decimal("500.25"))

        today = timezone.localdate()
        Transaction.objects.create(user=self.user, title="Lunch", category="food",
                                   txn_type="expense", amount=Decimal("125.25"), date=today)
        Transaction.objects.create(user=self.user, title="Yesterday", category="food",
                                   txn_type="expense", amount=Decimal("900"), date=today - timedelta(days=1))
        allowance = _daily_spending_allowance(today, self.profile)
        self.assertEqual(allowance["limit"], Decimal("500.25"))
        self.assertEqual(allowance["spent"], Decimal("125.25"))
        self.assertEqual(allowance["remaining"], Decimal("375.00"))
        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "Daily spending allowance")
        self.assertNotContains(dashboard, "Weekly spending check-in")

    def test_allowance_rejects_invalid_amount_and_can_be_cleared(self):
        self.profile.salary = Decimal("10000")
        self.profile.save(update_fields=["salary"])
        url = reverse("profile")
        for value in ("0", "-1", "NaN", "2.345", "10000000000"):
            response = self.client.post(url, {
                "action": "daily_allowance", "daily_spending_allowance": value,
            })
            self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.profile.daily_spending_allowance)
        self.client.post(url, {"action": "daily_allowance", "daily_spending_allowance": "150"})
        self.assertEqual(self.client.post(url, {"action": "clear_daily_allowance"}).status_code, 200)
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.daily_spending_allowance)

    def test_split_tracks_personal_share_and_retries_without_duplicates(self):
        payload = {
            "title": "Dinner", "amount": "1200.00", "category": "food",
            "date": timezone.localdate().isoformat(), "split_key": str(uuid4()),
            "shares": [{"name": "Alex", "amount": "300.00"}, {"name": "Sam", "amount": "500.00"}],
        }
        url = reverse("api_add_transaction")
        for _ in range(2):
            response = self.client.post(url, payload, content_type="application/json")
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json()["total_expense"], 400)
        parent = Transaction.objects.get(split_key=payload["split_key"])
        self.assertEqual(parent.amount, Decimal("400"))
        self.assertEqual(parent.split_shares.count(), 2)
        self.assertContains(self.client.get(reverse("lend")), "Dinner")
        share = parent.split_shares.get(title="Alex")
        paid = self.client.post(reverse("api_mark_lend_paid", args=[share.pk]))
        self.assertEqual(paid.status_code, 200)
        self.assertEqual(paid.json()["total_expense"], 400)
        self.assertEqual(paid.json()["total_income"], 0)
        share.refresh_from_db()
        self.assertTrue(share.is_settled)

        deleted = self.client.delete(reverse("api_delete_transaction", args=[parent.pk]))
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(Transaction.objects.filter(user=self.user).exists())

    def test_invalid_split_saves_no_expense_or_receivables(self):
        response = self.client.post(reverse("api_add_transaction"), {
            "title": "Dinner", "amount": "100.00", "category": "food",
            "date": timezone.localdate().isoformat(), "split_key": str(uuid4()),
            "shares": [{"name": "Alex", "amount": "120.00"}],
        }, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Transaction.objects.filter(user=self.user).exists())
