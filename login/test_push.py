import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import DailyAllowancePushDelivery, PhoneSubscription
from .push import send_due_allowance_push


class PushTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='push-user')
        self.client.force_login(self.user)

    def test_subscribe_rejects_untrusted_endpoint(self):
        response = self.client.post(reverse('push_subscribe'), data=json.dumps({
            'endpoint': 'https://localhost/private',
            'keys': {'p256dh': 'key', 'auth': 'auth'},
        }), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PhoneSubscription.objects.exists())

    @patch('login.push.webpush')
    def test_daily_push_once(self, webpush_mock):
        profile = self.user.profile
        profile.salary = Decimal('10000')
        profile.daily_spending_allowance = Decimal('200')
        profile.save(update_fields=['salary', 'daily_spending_allowance'])
        PhoneSubscription.objects.create(
            user=self.user,
            endpoint='https://fcm.googleapis.com/fcm/send/test',
            p256dh='test', auth='test',
        )
        now = timezone.make_aware(datetime(2026, 11, 15, 8, 0))
        self.assertEqual(send_due_allowance_push(now), 1)
        self.assertEqual(send_due_allowance_push(now), 0)
        self.assertEqual(webpush_mock.call_count, 1)
        self.assertEqual(DailyAllowancePushDelivery.objects.count(), 1)
