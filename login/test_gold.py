import io
import json
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from .gold import gold_quote
from .models import GoldPriceQuote


class GoldQuoteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.now = timezone.now()

    def fetch(self, price, updated=None):
        payload = {'symbol': 'XAU', 'currency': 'INR', 'price': price,
                   'updatedAt': (updated or self.now).isoformat()}
        with patch('login.gold.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
            return gold_quote()

    def test_rise_uses_24_hour_baseline_not_latest_refresh(self):
        GoldPriceQuote.objects.create(quoted_at=self.now - timedelta(hours=24), price=100)
        GoldPriceQuote.objects.create(quoted_at=self.now - timedelta(minutes=1), price=200)
        self.assertAlmostEqual(self.fetch(110)['change24h'], 10)

    def test_fall_and_unchanged(self):
        GoldPriceQuote.objects.create(quoted_at=self.now - timedelta(hours=24), price=100)
        self.assertAlmostEqual(self.fetch(90)['change24h'], -10)
        cache.clear()
        self.assertEqual(self.fetch(100)['change24h'], 0)

    def test_missing_or_old_baseline_is_unavailable(self):
        GoldPriceQuote.objects.create(quoted_at=self.now - timedelta(hours=25), price=100)
        self.assertIsNone(self.fetch(110)['change24h'])

    def test_stale_quote_has_no_direction(self):
        updated = self.now - timedelta(hours=1)
        GoldPriceQuote.objects.create(quoted_at=updated - timedelta(hours=24), price=100)
        self.assertIsNone(self.fetch(110, updated)['change24h'])

    def test_invalid_price_is_rejected(self):
        with self.assertRaises(ValueError):
            self.fetch(-10)
        self.assertFalse(GoldPriceQuote.objects.exists())
