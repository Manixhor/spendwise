from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .automation import run_due_jobs
from .models import AutomationState, ScheduledTestMail
from django.contrib.auth.models import User


class AutomationTests(TestCase):
    @patch('login.automation.call_command')
    def test_due_jobs_run_once_per_interval(self, command):
        now = timezone.now()
        self.assertTrue(run_due_jobs(now))
        self.assertFalse(run_due_jobs(now + timedelta(minutes=59)))
        self.assertTrue(run_due_jobs(now + timedelta(hours=1)))
        self.assertEqual(command.call_count, 4)
        self.assertEqual(AutomationState.objects.count(), 1)

    @patch('login.automation.call_command')
    def test_monthly_job_still_runs_if_reminders_fail(self, command):
        command.side_effect = [RuntimeError('mail unavailable'), None]
        self.assertTrue(run_due_jobs(timezone.now()))
        self.assertEqual(command.call_count, 2)

    @patch('login.automation.call_command')
    def test_scheduler_checks_at_local_midnight(self, command):
        now = timezone.make_aware(datetime(2026, 11, 7, 23, 30))
        self.assertTrue(run_due_jobs(now))
        state = AutomationState.objects.get(pk=1)
        self.assertEqual(timezone.localtime(state.next_check_at).hour, 0)
        self.assertEqual(timezone.localtime(state.next_check_at).minute, 0)

    @patch('login.automation.call_command')
    @patch('login.views.send_monthly_analysis_email')
    def test_one_time_mail_runs_at_eleven_pm_once(self, send_mail, command):
        user = User.objects.create_user(username='scheduled@example.com', email='scheduled@example.com')
        due = timezone.make_aware(datetime(2026, 11, 4, 23, 0))
        item = ScheduledTestMail.objects.create(user=user, report_month='2026-10', scheduled_at=due)
        self.assertTrue(run_due_jobs(due - timedelta(minutes=20)))
        self.assertFalse(item.sent_at)
        run_due_jobs(due)
        run_due_jobs(due + timedelta(minutes=1))
        send_mail.assert_called_once_with(user, '2026-10')
        item.refresh_from_db()
        self.assertIsNotNone(item.sent_at)
