import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import RecurringPayment, Transaction


class ChatbotToolsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="chat-user")
        self.other = User.objects.create_user(username="other-chat-user")
        self.client.force_login(self.user)
        self.url = reverse("chatbot_tools")

    def test_context_uses_only_signed_in_users_money(self):
        today = timezone.localdate()
        self.user.profile.salary = Decimal("10000")
        self.user.profile.daily_spending_allowance = Decimal("500")
        self.user.profile.save(update_fields=["salary", "daily_spending_allowance"])
        Transaction.objects.create(user=self.user, title="Lunch", txn_type="expense",
                                   category="food", amount=Decimal("120"), date=today)
        Transaction.objects.create(user=self.other, title="Private", txn_type="expense",
                                   category="food", amount=Decimal("900"), date=today)
        RecurringPayment.objects.create(user=self.user, name="Internet", kind="bill",
                                        amount=Decimal("800"), next_due=today + timedelta(days=2),
                                        day_of_month=(today + timedelta(days=2)).day)
        RecurringPayment.objects.create(user=self.other, name="Private bill", kind="bill",
                                        amount=Decimal("900"), next_due=today + timedelta(days=2),
                                        day_of_month=(today + timedelta(days=2)).day)
        data = self.client.get(self.url).json()
        self.assertEqual(Decimal(data["allowance"]["remaining"]), Decimal("380"))
        self.assertEqual([item["name"] for item in data["payments"]], ["Internet"])
        self.assertEqual([item["title"] for item in data["recent"]], ["Lunch"])

    def test_category_change_is_validated_and_user_scoped(self):
        today = timezone.localdate()
        own = Transaction.objects.create(user=self.user, title="Milk", txn_type="expense",
                                         category="other", amount=Decimal("50"), date=today)
        foreign = Transaction.objects.create(user=self.other, title="Private", txn_type="expense",
                                             category="other", amount=Decimal("50"), date=today)
        def update(txn_id, category):
            return self.client.post(self.url, json.dumps({"transaction_id": txn_id, "category": category}),
                                    content_type="application/json")
        self.assertEqual(update(foreign.pk, "groceries").status_code, 404)
        self.assertEqual(update(own.pk, "not-a-category").status_code, 400)
        self.assertEqual(update(own.pk, "groceries").status_code, 200)
        own.refresh_from_db()
        foreign.refresh_from_db()
        self.assertEqual(own.category, "groceries")
        self.assertEqual(foreign.category, "other")
