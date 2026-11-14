"""Deliver each user's daily allowance message once per local day."""

import logging
from datetime import time

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from .models import DailyAllowanceDelivery
from .templatetags.currency_filters import _format_with_symbol

logger = logging.getLogger(__name__)
SEND_TIME = time(8, 0)


def _eligible_users():
    return User.objects.filter(
        is_active=True,
        profile__email_is_verified=True,
        profile__salary__gt=0,
        profile__daily_spending_allowance__gt=0,
    ).exclude(email='').select_related('profile')


def send_allowance_email(user, day=None):
    day = day or timezone.localdate()
    profile = user.profile
    if not (user.is_active and user.email and profile.email_is_verified and
            profile.salary and profile.salary > 0 and
            profile.daily_spending_allowance and profile.daily_spending_allowance > 0):
        return False
    with transaction.atomic():
        delivery, _ = DailyAllowanceDelivery.objects.get_or_create(user=user, date=day)
        delivery = DailyAllowanceDelivery.objects.select_for_update().get(pk=delivery.pk)
        if delivery.email_sent_at:
            return False
        amount = _format_with_symbol(
            profile.daily_spending_allowance,
            symbol=profile.currency_symbol,
            use_indian_commas=profile.currency == 'inr',
        )
        subject = f'Your SpendWise allowance for today: {amount}'
        body = (
            f'Hello {user.first_name or user.username},\n\n'
            f'Your daily spending allowance for {day:%d %B %Y} is {amount}.\n'
            'You can check how much is left on your SpendWise dashboard.\n\n'
            'Have a good day,\nSpendWise'
        )
        EmailMultiAlternatives(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email]).send(fail_silently=False)
        delivery.email_sent_at = timezone.now()
        delivery.save(update_fields=['email_sent_at'])
    return True


def send_due_allowance_emails(now=None):
    now = now or timezone.now()
    local_now = timezone.localtime(now)
    if local_now.time() < SEND_TIME:
        return 0
    count = 0
    for user in _eligible_users().iterator():
        try:
            count += bool(send_allowance_email(user, local_now.date()))
        except Exception:
            logger.exception('Daily allowance email failed for user %s', user.pk)
    return count
