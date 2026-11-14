from datetime import datetime, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import MonthlyAnalysisDelivery, MonthlyAnalysisMailSetting
from .monthly_mailer import send_monthly_analysis_batch


class MonthlyDeliveryTests(TestCase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    @patch('login.management.commands.send_monthly_analysis_emails.timezone.localtime')
    @patch('login.management.commands.send_monthly_analysis_emails.send_monthly_analysis_batch')
    def test_default_schedule_sends_on_eighth(self, batch, localtime):
        setting = MonthlyAnalysisMailSetting.objects.create(pk=1)
        self.assertEqual(setting.send_day, 8)
        self.assertEqual(setting.send_time, time(0))
        batch.return_value = {'month': '2026-10', 'sent': 1, 'failed': 0, 'failures': []}
        localtime.return_value = timezone.make_aware(datetime(2026, 11, 7, 23, 59))
        call_command('send_monthly_analysis_emails')
        batch.assert_not_called()
        localtime.return_value = timezone.make_aware(datetime(2026, 11, 8, 0, 0))
        call_command('send_monthly_analysis_emails')
        batch.assert_called_once_with('2026-10', update_setting=True)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    @patch('login.management.commands.send_monthly_analysis_emails.timezone.localtime')
    @patch('login.management.commands.send_monthly_analysis_emails.send_monthly_analysis_batch')
    def test_missed_schedule_catches_up_later_in_month(self, batch, localtime):
        MonthlyAnalysisMailSetting.objects.create(pk=1, send_day=1, send_time=time(9))
        localtime.return_value = timezone.make_aware(datetime(2026, 11, 4, 10))
        batch.return_value = {'month': '2026-10', 'sent': 1, 'failed': 0, 'failures': []}
        call_command('send_monthly_analysis_emails')
        batch.assert_not_called()
        localtime.return_value = timezone.make_aware(datetime(2026, 11, 9, 10))
        call_command('send_monthly_analysis_emails')
        batch.assert_called_once_with('2026-10', update_setting=True)

    def test_staff_recipient_is_included(self):
        user = User.objects.create_user(username='staff@example.com', email='staff@example.com', is_staff=True)
        with patch('login.monthly_mailer.send_monthly_analysis_email', return_value=user.email) as sender:
            result = send_monthly_analysis_batch('2026-10')
        self.assertEqual(result['sent'], 1)
        sender.assert_called_once_with(user, '2026-10')

    def test_partial_failure_retries_only_failed_recipient(self):
        MonthlyAnalysisMailSetting.objects.create(pk=1)
        first = User.objects.create_user(username='first@example.com', email='first@example.com')
        second = User.objects.create_user(username='second@example.com', email='second@example.com')
        with patch('login.monthly_mailer.send_monthly_analysis_email', side_effect=[first.email, OSError('SMTP failure')]) as sender:
            result = send_monthly_analysis_batch('2026-10')
        self.assertEqual(result['failed'], 1)
        self.assertEqual(MonthlyAnalysisMailSetting.objects.get(pk=1).last_sent_month, '')
        self.assertTrue(MonthlyAnalysisDelivery.objects.filter(user=first, month='2026-10').exists())
        with patch('login.monthly_mailer.send_monthly_analysis_email', return_value=second.email) as sender:
            result = send_monthly_analysis_batch('2026-10')
        sender.assert_called_once_with(second, '2026-10')
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(MonthlyAnalysisMailSetting.objects.get(pk=1).last_sent_month, '2026-10')

    @override_settings(DEBUG=False, EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_missing_smtp_fails_in_production(self):
        with self.assertRaisesMessage(CommandError, 'SMTP is not configured'):
            call_command('send_monthly_analysis_emails')
