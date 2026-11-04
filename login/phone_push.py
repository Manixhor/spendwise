import base64
import json
import logging
from datetime import timedelta
from email.utils import parseaddr
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from pywebpush import WebPushException, webpush

from .models import PhoneNotificationDelivery, PhoneSubscription, PushKey, RecurringPayment

logger = logging.getLogger(__name__)


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _keys():
    key = ec.generate_private_key(ec.SECP256R1())
    private = _b64(key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    public = _b64(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    saved, _ = PushKey.objects.get_or_create(pk=1, defaults={'private_key': private, 'public_key': public})
    return saved


@login_required(login_url='/login/')
@require_GET
def push_public_key(request):
    return JsonResponse({'publicKey': _keys().public_key})


@login_required(login_url='/login/')
@require_POST
def subscribe_phone(request):
    try:
        data = json.loads(request.body)
        endpoint = data['endpoint']
        host = urlparse(endpoint).hostname or ''
        allowed = host in ('fcm.googleapis.com', 'fcmregistrations.googleapis.com', 'updates.push.services.mozilla.com', 'web.push.apple.com')
        if not allowed or not endpoint.startswith('https://') or len(endpoint) > 2000:
            raise ValueError('Unsupported push service.')
        keys = data['keys']
        p256dh, auth = keys['p256dh'], keys['auth']
        if not p256dh or not auth or len(p256dh) > 300 or len(auth) > 300:
            raise ValueError('Invalid subscription keys.')
        if PhoneSubscription.objects.filter(endpoint=endpoint).exclude(user=request.user).exists():
            raise ValueError('Subscription belongs to another account.')
        PhoneSubscription.objects.update_or_create(
            endpoint=endpoint, defaults={'user': request.user, 'p256dh': p256dh, 'auth': auth},
        )
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Could not save phone notifications.'}, status=400)
    return JsonResponse({'ok': True})


@login_required(login_url='/login/')
@require_POST
def unsubscribe_phone(request):
    try:
        endpoint = json.loads(request.body).get('endpoint', '')
    except (ValueError, TypeError):
        endpoint = ''
    PhoneSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return JsonResponse({'ok': True})


def send_phone_reminders(today=None):
    today = today or timezone.localdate()
    subscriptions = PhoneSubscription.objects.select_related('user').all()
    if not subscriptions.exists():
        return 0
    key = _keys()
    contact = parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
    sent = 0
    for subscription in subscriptions:
        payments = RecurringPayment.objects.filter(
            user=subscription.user, active=True,
            next_due__gte=today, next_due__lte=today + timedelta(days=3),
        )
        for payment in payments:
            if PhoneNotificationDelivery.objects.filter(subscription=subscription, payment=payment, due_date=payment.next_due).exists():
                continue
            payload = json.dumps({'title': 'SpendWise payment reminder', 'body': f'{payment.name} is due on {payment.next_due:%d %b}.', 'url': '/planner/'})
            try:
                webpush(
                    subscription_info={'endpoint': subscription.endpoint, 'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth}},
                    data=payload, vapid_private_key=key.private_key,
                    vapid_claims={'sub': f'mailto:{contact}'}, ttl=86400, timeout=10,
                )
            except WebPushException as exc:
                if exc.response is not None and exc.response.status_code in (404, 410):
                    subscription.delete()
                    break
                logger.warning('Phone push delivery failed', exc_info=True)
            except Exception:
                logger.warning('Phone push delivery failed', exc_info=True)
            else:
                PhoneNotificationDelivery.objects.get_or_create(subscription=subscription, payment=payment, due_date=payment.next_due)
                sent += 1
    return sent
