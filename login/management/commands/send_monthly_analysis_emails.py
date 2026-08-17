from django.core.management.base import BaseCommand
from django.utils import timezone

from login.models import MonthlyAnalysisMailSetting
from login.monthly_mailer import send_monthly_analysis_batch


class Command(BaseCommand):
    help = "Send SpendWise monthly analysis emails to users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--month",
            help="Report month in YYYY-MM format. Defaults to current month.",
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
            month = local_now.strftime("%Y-%m")

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

        result = send_monthly_analysis_batch(month)
        for failure in result["failures"]:
            self.stderr.write(self.style.ERROR(f"Failed: {failure}"))

        self.stdout.write(
            self.style.SUCCESS(
                "Monthly analysis batch complete. "
                f"Month={month}, sent={result['sent']}, failed={result['failed']}."
            )
        )
