from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Transaction
from .views import _daily_spending_allowance, _weekly_spending_check_in


class SpendingToolsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="spending-tools")
        self.profile = self.user.profile
        self.client.force_login(self.user)

    def test_allowance_includes_today_and_reserves_savings(self):
        self.profile.salary = Decimal("10000")
        self.profile.target_savings = Decimal("2000")
        stats = {"excess_income": Decimal("500"), "total_expense": Decimal("2500")}
        allowance = _daily_spending_allowance(date(2028, 2, 20), self.profile, stats)
        self.assertEqual(allowance["days"], 10)
        self.assertEqual(allowance["per_day"], Decimal("600.00"))
        stats["total_expense"] = Decimal("8600")
        allowance = _daily_spending_allowance(date(2028, 2, 29), self.profile, stats)
        self.assertEqual(allowance["days"], 1)
        self.assertEqual(allowance["per_day"], 0)
        self.assertEqual(allowance["over"], 100)

    def test_weekly_check_in_compares_two_seven_day_windows(self):
        today = date(2026, 11, 5)
        for age, category, amount in [(0, "food", 500), (6, "food", 100),
                                      (7, "food", 200), (13, "rent", 300),
                                      (14, "food", 1000)]:
            Transaction.objects.create(
                user=self.user, title=f"Expense {age}", category=category,
                txn_type="expense", amount=amount, date=today - timedelta(days=age),
            )
        report = _weekly_spending_check_in(self.user, today)
        self.assertEqual((report["current"], report["previous"]), (600, 500))
        self.assertEqual(report["category"], "Food")
        self.assertEqual(report["category_difference"], 400)
        self.assertEqual([txn.title for txn in report["current_examples"]], ["Expense 0", "Expense 6"])

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
