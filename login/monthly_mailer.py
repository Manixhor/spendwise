from datetime import date, timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from .models import MonthlyAnalysisMailSetting
from .views import send_monthly_analysis_email


def previous_month(today: date) -> str:
    first_day = today.replace(day=1)
    previous = first_day - timedelta(days=1)
    return previous.strftime("%Y-%m")


def send_monthly_analysis_batch(month: str, update_setting: bool = True) -> dict:
    users = User.objects.filter(is_active=True, email__gt="").order_by("id")
    sent = 0
    failed = 0
    failures = []

    for user in users:
        try:
            recipient = send_monthly_analysis_email(user, month)
        except Exception as exc:
            failed += 1
            failures.append(f"{user.email or user.id}: {exc}")
            continue

        sent += 1

    if update_setting and sent:
        setting, _ = MonthlyAnalysisMailSetting.objects.get_or_create(pk=1)
        setting.last_sent_month = month
        setting.last_sent_at = timezone.now()
        setting.save(update_fields=["last_sent_month", "last_sent_at", "updated_at"])

    return {
        "month": month,
        "sent": sent,
        "failed": failed,
        "failures": failures,
    }
