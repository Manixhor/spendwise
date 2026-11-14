"""Web Push subscriptions and daily allowance notifications."""

import base64
import json
import logging

from cryptography.hazmat.primitives import serialization
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from .models import DailyAllowancePushDelivery, PhoneSubscription, PushKey
from .templatetags.currency_filters import _format_with_symbol

logger = logging.getLogger(__name__)


def _push_key():
    key = PushKey.objects.filter(pk=1).first()
    if key:
        return key
    vapid = Vapid()
    vapid.generate_keys()
    raw_public = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    with transaction.atomic():
        key, _ = PushKey.objects.get_or_create(
            pk=1,
            defaults={
                'private_key': vapid.private_pem().decode(),
                'public_key': base64.urlsafe_b64encode(raw_public).rstrip(b'=').decode(),
            },
        )
    return key


def public_push_key():
    return _push_key().public_key


def send_due_allowance_push(now=None):
    from .daily_allowance import SEND_TIME
    now = now or timezone.now()
    local_now = timezone.localtime(now)
    if local_now.time() < SEND_TIME:
        return 0
    subscriptions = PhoneSubscription.objects.filter(
        user__is_active=True,
        user__profile__salary__gt=0,
        user__profile__daily_spending_allowance__gt=0,
    ).select_related('user__profile')
    count = 0
    for subscription in subscriptions.iterator():
        if DailyAllowancePushDelivery.objects.filter(subscription=subscription, date=local_now.date()).exists():
            continue
        profile = subscription.user.profile
        amount = _format_with_symbol(
            profile.daily_spending_allowance,
            symbol=profile.currency_symbol,
            use_indian_commas=profile.currency == 'inr',
        )
        try:
            vapid = Vapid.from_pem(_push_key().private_key.encode())
            webpush(
                subscription_info={
                    'endpoint': subscription.endpoint,
                    'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth},
                },
                data=json.dumps({'title': 'SpendWise daily allowance',
                                 'body': f'Your allowance for today is {amount}.',
                                 'url': '/dashboard/'}),
                vapid_private_key=vapid,
                vapid_claims={'sub': f'mailto:{settings.PRIVACY_CONTACT_EMAIL}'},
                timeout=10,
            )
            DailyAllowancePushDelivery.objects.get_or_create(
                subscription=subscription, date=local_now.date(),
            )
            count += 1
        except WebPushException as exc:
            if exc.response is not None and exc.response.status_code in (404, 410):
                subscription.delete()
            else:
                logger.exception('Daily allowance push failed for subscription %s', subscription.pk)
        except Exception:
            logger.exception('Daily allowance push failed for subscription %s', subscription.pk)
    return count
