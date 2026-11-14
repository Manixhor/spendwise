from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .daily_allowance import send_due_allowance_emails
from .models import DailyAllowanceDelivery


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DailyAllowanceEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='daily', email='daily@example.com')
        self.profile = self.user.profile
        self.profile.salary = Decimal('10000')
        self.profile.email_is_verified = True
        self.profile.save(update_fields=['salary', 'email_is_verified'])
        self.client.force_login(self.user)

    def test_first_allowance_emails_once_and_popup_api_edits(self):
        response = self.client.post(reverse('api_daily_allowance'),
                                    data='{"amount":"200.00"}', content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['mail_sent'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('200', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].alternatives[0].mimetype, 'text/html')
        self.assertIn('Open dashboard', mail.outbox[0].alternatives[0].content)
        self.client.post(reverse('api_daily_allowance'),
                         data='{"amount":"250.00"}', content_type='application/json')
        self.assertEqual(len(mail.outbox), 1)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.daily_spending_allowance, Decimal('250'))

    def test_daily_job_waits_until_eight_and_sends_once(self):
        self.profile.daily_spending_allowance = Decimal('300')
        self.profile.save(update_fields=['daily_spending_allowance'])
        before = timezone.make_aware(datetime(2026, 11, 15, 7, 59))
        self.assertEqual(send_due_allowance_emails(before), 0)
        self.assertEqual(send_due_allowance_emails(before + timedelta(minutes=1)), 1)
        self.assertEqual(send_due_allowance_emails(before + timedelta(hours=2)), 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(DailyAllowanceDelivery.objects.count(), 1)

    def test_unverified_email_is_not_sent(self):
        self.profile.email_is_verified = False
        self.profile.daily_spending_allowance = Decimal('300')
        self.profile.save(update_fields=['email_is_verified', 'daily_spending_allowance'])
        now = timezone.make_aware(datetime(2026, 11, 15, 8, 0))
        self.assertEqual(send_due_allowance_emails(now), 0)
        self.assertFalse(mail.outbox)
