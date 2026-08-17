from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from login.models import MonthlyAnalysisMailSetting
from login.views import send_monthly_analysis_email


def _previous_month(today: date) -> str:
    first_day = today.replace(day=1)
    previous = first_day - timedelta(days=1)
    return previous.strftime("%Y-%m")


class Command(BaseCommand):
    help = "Send SpendWise monthly analysis emails to users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--month",
            help="Report month in YYYY-MM format. Defaults to current month for --now, previous month for scheduled runs.",
        )
        parser.add_argument(
            "--now",
            action="store_true",
            help="Send immediately, ignoring configured day and time but respecting enabled unless --force is used.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Send even if monthly email is disabled or already sent for the month.",
        )

    def handle(self, *args, **options):
        setting, _ = MonthlyAnalysisMailSetting.objects.get_or_create(pk=1)
        local_now = timezone.localtime()
        month = options.get("month")
        send_now = options["now"]
        force = options["force"]

        if not month:
            month = local_now.strftime("%Y-%m") if send_now else _previous_month(local_now.date())

        if not force and not setting.enabled:
            self.stdout.write(self.style.WARNING("Monthly analysis emails are disabled in admin."))
            return

        if not send_now and not force:
            if local_now.day != setting.send_day:
                self.stdout.write(
                    self.style.WARNING(
                        f"Not scheduled today. Configured day is {setting.send_day}."
                    )
                )
                return
            if local_now.time().replace(microsecond=0) < setting.send_time:
                self.stdout.write(
                    self.style.WARNING(
                        f"Not time yet. Configured send time is {setting.send_time:%H:%M}."
                    )
                )
                return
            if setting.last_sent_month == month:
                self.stdout.write(
                    self.style.WARNING(f"Monthly analysis already sent for {month}.")
                )
                return

        users = User.objects.filter(is_active=True, email__gt="").order_by("id")
        sent = 0
        failed = 0

        for user in users:
            try:
                recipient = send_monthly_analysis_email(user, month)
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"Failed for user {user.id} ({user.email}): {exc}")
                )
                continue

            sent += 1
            self.stdout.write(f"Sent {month} monthly analysis to {recipient}")

        if sent:
            setting.last_sent_month = month
            setting.last_sent_at = timezone.now()
            setting.save(update_fields=["last_sent_month", "last_sent_at", "updated_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Monthly analysis batch complete. Month={month}, sent={sent}, failed={failed}."
            )
        )
