from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.conf import settings
from django.utils import timezone

from login.models import MonthlyAnalysisMailSetting
from login.monthly_mailer import send_due_monthly_analysis_emails, send_monthly_analysis_batch


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
        local_now = timezone.localtime()
        month = options.get("month")
        send_now = options["now"]
        force = options["force"]

        scheduled_run = not (month or send_now or force)
        if scheduled_run:
            result = send_due_monthly_analysis_emails(timezone.now())
            if result is None:
                self.stdout.write(self.style.WARNING('No monthly schedule is due yet, or automatic emails are disabled.'))
                return
            month = result['month']
        else:
            setting, _ = MonthlyAnalysisMailSetting.objects.get_or_create(pk=1)
            if not force and not setting.enabled:
                self.stdout.write(self.style.WARNING('Monthly analysis emails are disabled in admin.'))
                return
            month = month or local_now.strftime('%Y-%m')
            result = send_monthly_analysis_batch(month, update_setting=False)
        for failure in result["failures"]:
            self.stderr.write(self.style.ERROR(f"Failed: {failure}"))

        if result['failed']:
            raise CommandError(f"Monthly analysis delivery failed for {result['failed']} recipient(s); retry on the next cron run.")

        self.stdout.write(
            self.style.SUCCESS(
                "Monthly analysis batch complete. "
                f"Month={month}, sent={result['sent']}, failed={result['failed']}."
            )
        )
