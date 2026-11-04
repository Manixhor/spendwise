from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.conf import settings
from django.utils import timezone
from datetime import time

from login.models import MonthlyAnalysisMailSetting
from login.monthly_mailer import previous_month, send_monthly_analysis_batch


class Command(BaseCommand):
    help = "Send SpendWise monthly analysis emails to users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--month",
            help="Report month in YYYY-MM format. Defaults to the previous completed month for scheduled runs.",
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
        if not settings.DEBUG and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            raise CommandError('SMTP is not configured for this job. Set SMTP_USERNAME and SMTP_PASSWORD.')
        setting, _ = MonthlyAnalysisMailSetting.objects.get_or_create(pk=1)
        local_now = timezone.localtime()
        month = options.get("month")
        send_now = options["now"]
        force = options["force"]

        scheduled_run = not (month or send_now or force)

        if not month:
            month = (
                local_now.strftime("%Y-%m")
                if send_now or force
                else previous_month(local_now.date())
            )

        if not force and not setting.enabled:
            self.stdout.write(self.style.WARNING("Monthly analysis emails are disabled in admin."))
            return

        should_send = send_now or force
        reason = None

        if not should_send:
            primary_due = local_now.day > setting.send_day or (
                local_now.day == setting.send_day and local_now.time().replace(microsecond=0) >= setting.send_time
            )
            if primary_due and setting.last_sent_month != month:
                reason = 'primary'
                should_send = True
            else:
                self.stdout.write(self.style.WARNING('No unsent monthly schedule is due yet.'))
                return

        if not should_send:
            self.stdout.write(self.style.WARNING("No schedule matched."))
            return

        result = send_monthly_analysis_batch(month, update_setting=(reason == 'primary' and scheduled_run))
        for failure in result["failures"]:
            self.stderr.write(self.style.ERROR(f"Failed: {failure}"))

        if result['failed']:
            raise CommandError(f"Monthly analysis delivery failed for {result['failed']} recipient(s); retry on the next cron run.")

        if scheduled_run and not (send_now or force) and (result['sent'] or result.get('skipped', 0)):
            if reason == 'primary':
                setting.last_sent_month = month
                setting.last_sent_at = timezone.now()
                setting.save(update_fields=["last_sent_month", "last_sent_at", "updated_at"])

        self.stdout.write(
            self.style.SUCCESS(
                "Monthly analysis batch complete. "
                f"Month={month}, sent={result['sent']}, failed={result['failed']}."
            )
        )
