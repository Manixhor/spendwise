"""Run due SpendWise jobs inside a running web service.

The database lease lets multiple web workers check safely. The first check runs on
startup, and later checks run hourly while the service is running.
"""
import logging
import os
import sys
import threading
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management import call_command
from django.db import transaction
from django.db import close_old_connections
from django.utils import timezone

from .models import AutomationState, ScheduledTestMail

logger = logging.getLogger(__name__)
_check_interval = timedelta(hours=1)
_start_lock = threading.Lock()
_thread = None
_thread_pid = None


def run_due_jobs(now=None):
    now = now or timezone.now()
    send_due_test_mails(now)
    local_now = timezone.localtime(now)
    next_midnight = timezone.make_aware(
        datetime.combine(local_now.date() + timedelta(days=1), time.min),
        timezone.get_current_timezone(),
    )
    next_check = min(now + _check_interval, next_midnight)
    AutomationState.objects.get_or_create(pk=1, defaults={'next_check_at': now})
    claimed = AutomationState.objects.filter(pk=1, next_check_at__lte=now).update(
        next_check_at=next_check
    )
    if not claimed:
        return False
    try:
        call_command('send_monthly_analysis_emails')
    except Exception:
        logger.exception('SpendWise monthly analysis job failed')
    try:
        from .daily_allowance import send_due_allowance_emails
        send_due_allowance_emails(now)
    except Exception:
        logger.exception('SpendWise daily allowance job failed')
    try:
        from .push import send_due_allowance_push
        send_due_allowance_push(now)
    except Exception:
        logger.exception('SpendWise daily allowance push job failed')
    return True


def send_due_test_mails(now):
    from .views import send_monthly_analysis_email
    due_ids = list(ScheduledTestMail.objects.filter(sent_at__isnull=True, scheduled_at__lte=now).values_list('pk', flat=True))
    for item_id in due_ids:
        with transaction.atomic():
            item = ScheduledTestMail.objects.select_for_update().select_related('user').get(pk=item_id)
            if item.sent_at is not None:
                continue
            try:
                if not settings.DEBUG and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
                    raise RuntimeError('SMTP is not configured')
                send_monthly_analysis_email(item.user, item.report_month)
            except Exception:
                logger.exception('Scheduled SpendWise test email failed')
                item.last_error = 'Email delivery failed; retrying on the next check.'
                item.save(update_fields=['last_error'])
            else:
                item.sent_at = timezone.now()
                item.last_error = ''
                item.save(update_fields=['sent_at', 'last_error'])


def _loop():
    while True:
        close_old_connections()
        try:
            # Gold has its own per-minute database lease; mail keeps its hourly lease.
            from .gold import collect_gold_quote
            try:
                collect_gold_quote()
            except Exception:
                logger.exception('SpendWise gold collection failed; retrying next minute')
            run_due_jobs()
        except Exception:
            # A new release can start before migrations finish. Retry after a minute.
            logger.exception('SpendWise automatic job check failed')
        finally:
            close_old_connections()
        threading.Event().wait(60)


def ensure_scheduler():
    global _thread, _thread_pid
    if settings.DEBUG or 'test' in sys.argv[1:] or 'PYTEST_CURRENT_TEST' in os.environ:
        return
    with _start_lock:
        pid = os.getpid()
        if _thread_pid != pid or _thread is None or not _thread.is_alive():
            _thread_pid = pid
            _thread = threading.Thread(target=_loop, name='spendwise-automation', daemon=True)
            _thread.start()


class AutomationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ensure_scheduler()
        return self.get_response(request)
