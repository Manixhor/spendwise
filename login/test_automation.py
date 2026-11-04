from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .automation import run_due_jobs
from .models import AutomationState


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
