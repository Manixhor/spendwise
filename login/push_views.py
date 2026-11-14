import json
from urllib.parse import urlparse

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import PhoneSubscription
from .push import public_push_key

ALLOWED_PUSH_HOSTS = {
    'fcm.googleapis.com',
    'fcmregistrations.googleapis.com',
    'updates.push.services.mozilla.com',
    'web.push.apple.com',
    'notify.windows.com',
}


@login_required(login_url='/login/')
@require_GET
def push_key(request):
    return JsonResponse({'publicKey': public_push_key()})


@login_required(login_url='/login/')
@require_POST
def push_subscribe(request):
    try:
        data = json.loads(request.body)
        endpoint = data['endpoint']
        p256dh = data['keys']['p256dh']
        auth = data['keys']['auth']
        parsed = urlparse(endpoint)
        if (parsed.scheme != 'https' or parsed.hostname not in ALLOWED_PUSH_HOSTS or
                len(endpoint) > 2048 or not p256dh or not auth or
                len(p256dh) > 256 or len(auth) > 256):
            raise ValueError
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid notification subscription.'}, status=400)
    PhoneSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={'user': request.user, 'p256dh': p256dh, 'auth': auth},
    )
    return JsonResponse({'success': True})


@login_required(login_url='/login/')
@require_POST
def push_unsubscribe(request):
    try:
        endpoint = json.loads(request.body)['endpoint']
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid notification subscription.'}, status=400)
    PhoneSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return JsonResponse({'success': True})
