from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .models import MonthlyAnalysisMailSetting, MonthlyAnalysisDelivery
from .views import send_monthly_analysis_email


def previous_month(today: date) -> str:
    first_day = today.replace(day=1)
    previous = first_day - timedelta(days=1)
    return previous.strftime("%Y-%m")


def send_monthly_analysis_batch(month: str, update_setting: bool = True) -> dict:
    """Send `month` analysis to every eligible user.

    `update_setting` records each recipient's successful delivery. Manual
    current-month previews do not count toward the scheduled completed month.
    """
    users = User.objects.filter(is_active=True).exclude(email='').order_by('id')
    sent = 0
    failed = 0
    skipped = 0
    failures = []

    for user in users:
        try:
            if update_setting:
                with transaction.atomic():
                    delivery, _ = MonthlyAnalysisDelivery.objects.get_or_create(user=user, month=month)
                    delivery = MonthlyAnalysisDelivery.objects.select_for_update().get(pk=delivery.pk)
                    if delivery.sent_at:
                        skipped += 1
                        continue
                    send_monthly_analysis_email(user, month)
                    delivery.sent_at = timezone.now()
                    delivery.save(update_fields=['sent_at'])
            else:
                send_monthly_analysis_email(user, month)
        except Exception as exc:
            failed += 1
            failures.append(f"{user.email or user.id}: {exc}")
            continue

        sent += 1

    if update_setting and not failed and (sent or skipped):
        setting, _ = MonthlyAnalysisMailSetting.objects.get_or_create(pk=1)
        if sent or setting.last_sent_month != month:
            setting.last_sent_month = month
            setting.last_sent_at = timezone.now()
            setting.save(update_fields=["last_sent_month", "last_sent_at", "updated_at"])

    return {
        "month": month,
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    }


def send_due_monthly_analysis_emails(now=None) -> dict | None:
    """Retry each unsent recipient from the 8th, even if the batch was marked sent."""
    local_now = timezone.localtime(now or timezone.now())
    if local_now.day < 8:
        return None
    if not settings.DEBUG and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
        raise RuntimeError('SMTP is not configured for monthly analysis email')
    setting, _ = MonthlyAnalysisMailSetting.objects.get_or_create(pk=1)
    if not setting.enabled:
        return None
    return send_monthly_analysis_batch(previous_month(local_now.date()), update_setting=True)
