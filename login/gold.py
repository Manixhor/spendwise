"""Live INR gold quotes and a persisted rolling 24-hour baseline."""
import json
import math
import urllib.request
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET

from .models import GoldPriceQuote


def gold_quote():
    cached = cache.get('gold-inr-quote')
    if cached is not None:
        return cached
    request = urllib.request.Request('https://api.gold-api.com/price/XAU/INR',
                                     headers={'User-Agent': 'SpendWise/1.0'})
    with urllib.request.urlopen(request, timeout=8) as response:
        quote = json.load(response)
    price = quote.get('price')
    updated = parse_datetime(quote.get('updatedAt', ''))
    if (quote.get('symbol') != 'XAU' or quote.get('currency') != 'INR'
            or isinstance(price, bool) or not isinstance(price, (int, float))
            or not math.isfinite(price) or price <= 0 or updated is None
            or timezone.is_naive(updated) or updated > timezone.now() + timedelta(minutes=1)):
        raise ValueError('Invalid gold quote')
    GoldPriceQuote.objects.get_or_create(quoted_at=updated, defaults={'price': price})
    target = updated - timedelta(hours=24)
    baseline = GoldPriceQuote.objects.filter(
        quoted_at__lte=target, quoted_at__gte=target - timedelta(minutes=5),
    ).order_by('-quoted_at').first()
    fresh = timezone.now() - updated <= timedelta(minutes=5)
    change = (price / baseline.price - 1) * 100 if baseline and fresh else None
    payload = {'symbol': 'XAU', 'currency': 'INR', 'price': price,
               'updatedAt': updated.isoformat(), 'change24h': change,
               'baselineAt': baseline.quoted_at.isoformat() if baseline else None}
    GoldPriceQuote.objects.filter(quoted_at__lt=timezone.now() - timedelta(days=3)).delete()
    cache.set('gold-inr-quote', payload, 30)
    return payload


@login_required(login_url='/login/')
@require_GET
def api_gold_price(request):
    try:
        response = JsonResponse(gold_quote())
    except (OSError, ValueError, TypeError, KeyError):
        response = JsonResponse({'error': 'Gold price temporarily unavailable'}, status=503)
    response['Cache-Control'] = 'no-store'
    return response
