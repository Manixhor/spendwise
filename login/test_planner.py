from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import MoneyAccount, PhoneNotificationDelivery, PhoneSubscription, RecurringPayment, Transaction, UserProfile
from .planner import next_month
from .phone_push import send_phone_reminders


class PlannerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='planner@example.com', password='StrongPass123!')
        self.client.force_login(self.user)

    def test_month_end_due_date_does_not_drift(self):
        self.assertEqual(next_month(date(2026, 1, 31), 31), date(2026, 2, 28))
        self.assertEqual(next_month(date(2026, 2, 28), 31), date(2026, 3, 31))

    def test_auto_payment_records_once_and_advances(self):
        item = RecurringPayment.objects.create(
            user=self.user, name='Netflix', kind='subscription', amount=Decimal('12.00'),
            category='entertainment', next_due=timezone.localdate(),
            day_of_month=timezone.localdate().day, auto_record=True,
        )
        self.client.get(reverse('dashboard'))
        self.client.get(reverse('dashboard'))
        item.refresh_from_db()
        self.assertEqual(Transaction.objects.filter(user=self.user, title='Netflix').count(), 1)
        self.assertGreater(item.next_due, timezone.localdate())

    def test_overdue_auto_payment_records_each_due_month(self):
        previous = timezone.localdate() - timedelta(days=65)
        item = RecurringPayment.objects.create(
            user=self.user, name='Music', kind='subscription', amount=Decimal('5.00'),
            next_due=previous, day_of_month=previous.day, auto_record=True,
        )
        self.client.get(reverse('planner'))
        item.refresh_from_db()
        self.assertGreater(item.next_due, timezone.localdate())
        self.assertGreaterEqual(Transaction.objects.filter(user=self.user, title='Music').count(), 2)

    def test_account_is_available_on_dashboard_and_transaction(self):
        account = MoneyAccount.objects.create(user=self.user, name='Main bank', kind='bank')
        self.assertContains(self.client.get(reverse('dashboard')), 'Main bank')
        response = self.client.post(reverse('api_add_transaction'), data={
            'title': 'Lunch', 'amount': '10', 'txn_type': 'expense',
            'category': 'food', 'account': account.pk, 'date': '2026-11-01',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.get(user=self.user).account, account)

    def test_dashboard_shows_payment_calendar(self):
        RecurringPayment.objects.create(
            user=self.user, name='Rent', kind='bill', amount=Decimal('100.00'),
            next_due=timezone.localdate(), day_of_month=timezone.localdate().day,
        )
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Bills this month')
        self.assertContains(response, 'Rent')

    def test_phone_subscription_and_reminder_send_once(self):
        endpoint = 'https://fcm.googleapis.com/fcm/send/test-subscription'
        response = self.client.post(reverse('subscribe_phone'), data=json.dumps({
            'endpoint': endpoint, 'keys': {'p256dh': 'test-key', 'auth': 'test-auth'},
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        payment = RecurringPayment.objects.create(
            user=self.user, name='Rent', kind='bill', amount=Decimal('100.00'),
            next_due=timezone.localdate(), day_of_month=timezone.localdate().day,
        )
        with patch('login.phone_push.webpush') as send:
            self.assertEqual(send_phone_reminders(), 1)
            self.assertEqual(send_phone_reminders(), 0)
        self.assertEqual(send.call_count, 1)
        self.assertTrue(PhoneNotificationDelivery.objects.filter(payment=payment).exists())
        self.client.post(reverse('unsubscribe_phone'), data=json.dumps({'endpoint': endpoint}), content_type='application/json')
        self.assertFalse(PhoneSubscription.objects.filter(endpoint=endpoint).exists())

    def test_phone_subscription_rejects_untrusted_endpoint(self):
        response = self.client.post(reverse('subscribe_phone'), data=json.dumps({
            'endpoint': 'https://example.com/collect', 'keys': {'p256dh': 'key', 'auth': 'auth'},
        }), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PhoneSubscription.objects.exists())

    def test_scheduled_command_records_automatic_payment(self):
        RecurringPayment.objects.create(
            user=self.user, name='Internet', kind='bill', amount=Decimal('20.00'),
            next_due=timezone.localdate(), day_of_month=timezone.localdate().day,
            auto_record=True,
        )
        call_command('send_spendwise_reminders')
        call_command('send_spendwise_reminders')
        self.assertEqual(Transaction.objects.filter(user=self.user, title='Internet').count(), 1)

    def test_account_cannot_be_assigned_from_another_user(self):
        other = User.objects.create_user(username='other@example.com')
        account = MoneyAccount.objects.create(user=other, name='Other bank', kind='bank')
        response = self.client.post(reverse('api_add_transaction'), data={
            'title': 'Coffee', 'amount': '10', 'txn_type': 'expense',
            'category': 'food', 'account': account.pk, 'date': '2026-11-01',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_import_is_available_from_planner(self):
        csv = b'Date,Description,Amount\n2026-11-01,Coffee,10.00\n'
        response = self.client.post(reverse('planner'), {
            'action': 'import', 'file': SimpleUploadedFile('statement.csv', csv, content_type='text/csv'),
        })
        self.assertRedirects(response, reverse('planner'))
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_email_reminder_is_opt_in_and_sent_once(self):
        self.user.email = 'planner@example.com'
        self.user.save(update_fields=['email'])
        profile = UserProfile.objects.get(user=self.user)
        profile.email_is_verified = True
        profile.reminders_enabled = True
        profile.save(update_fields=['email_is_verified', 'reminders_enabled'])
        RecurringPayment.objects.create(
            user=self.user, name='Rent', kind='bill', amount=Decimal('100.00'),
            next_due=timezone.localdate(), day_of_month=timezone.localdate().day,
        )
        call_command('send_spendwise_reminders')
        call_command('send_spendwise_reminders')
        self.assertEqual(len(mail.outbox), 1)
