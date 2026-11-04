from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from login.models import RecurringPayment, Transaction, UserProfile
from login.planner import record_automatic_payments
from login.phone_push import send_phone_reminders
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Send opted-in payment and budget reminder emails. Run daily.'

    def handle(self, *args, **options):
        today = timezone.localdate()
        sent = 0
        failed = 0
        send_phone_reminders(today)
        user_ids = RecurringPayment.objects.filter(active=True, auto_record=True, next_due__lte=today).values_list('user_id', flat=True).distinct()
        for user in get_user_model().objects.filter(pk__in=user_ids):
            record_automatic_payments(user, today)
        for profile in UserProfile.objects.select_related('user').filter(reminders_enabled=True, user__is_active=True):
            user = profile.user
            if not user.email or not profile.email_is_verified:
                continue
            for item in RecurringPayment.objects.filter(user=user, active=True, next_due__lte=today + timedelta(days=3)):
                if item.last_reminded_due == item.next_due:
                    continue
                try:
                    send_mail(
                        f'SpendWise reminder: {item.name}',
                        f'{item.name} is due on {item.next_due:%d %b %Y}. Amount: {profile.currency_symbol}{item.amount}. Open SpendWise to review it.',
                        settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False,
                    )
                except Exception:
                    failed += 1
                    continue
                item.last_reminded_due = item.next_due
                item.save(update_fields=['last_reminded_due'])
                sent += 1
            if profile.salary and profile.salary > 0:
                month = today.strftime('%Y-%m')
                if profile.last_budget_reminder_month != month:
                    spent = Transaction.objects.filter(user=user, txn_type='expense', date__year=today.year, date__month=today.month).aggregate(total=Sum('amount'))['total'] or Decimal('0')
                    if spent >= profile.salary * Decimal('0.8'):
                        try:
                            send_mail(
                                'SpendWise budget reminder',
                                f'You have spent {profile.currency_symbol}{spent} this month, at least 80% of your salary budget. Open SpendWise to review your spending.',
                                settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False,
                            )
                        except Exception:
                            failed += 1
                        else:
                            profile.last_budget_reminder_month = month
                            profile.save(update_fields=['last_budget_reminder_month'])
                            sent += 1
        self.stdout.write(f'Reminders sent: {sent}; failed: {failed}')
