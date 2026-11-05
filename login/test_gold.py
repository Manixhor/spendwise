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


class GoldCollectionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.now = timezone.now()

    @patch('login.gold.gold_quote')
    def test_multiple_workers_collect_only_once_per_minute(self, fetch):
        from .gold import collect_gold_quote
        self.assertTrue(collect_gold_quote(self.now))
        self.assertFalse(collect_gold_quote(self.now + timedelta(seconds=59)))
        self.assertTrue(collect_gold_quote(self.now + timedelta(minutes=1)))
        self.assertEqual(fetch.call_count, 2)

    @patch('login.gold.gold_quote')
    def test_failed_collection_retries_next_minute(self, fetch):
        from .gold import collect_gold_quote
        fetch.side_effect = [OSError('unavailable'), {'price': 100}]
        with self.assertRaises(OSError):
            collect_gold_quote(self.now)
        self.assertFalse(collect_gold_quote(self.now + timedelta(seconds=30)))
        self.assertTrue(collect_gold_quote(self.now + timedelta(minutes=1)))

    def test_history_collected_without_visitors_is_available_on_first_visit(self):
        from .gold import collect_gold_quote
        from django.contrib.auth.models import User
        from django.test import override_settings
        from django.urls import reverse
        for updated, price in [(self.now - timedelta(hours=24), 100), (self.now, 110)]:
            quote = {'symbol': 'XAU', 'currency': 'INR', 'price': price, 'updatedAt': updated.isoformat()}
            cache.clear()
            with patch('login.gold.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(quote).encode())):
                self.assertTrue(collect_gold_quote(updated))
        user = User.objects.create_user(username='gold-visitor')
        self.client.force_login(user)
        with override_settings(SECURE_SSL_REDIRECT=False):
            response = self.client.get(reverse('api_gold_price'))
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.json()['change24h'], 10)

    @patch('login.gold.collect_gold_quote', return_value=False)
    def test_management_command_can_run_under_cron(self, collect):
        from django.core.management import call_command
        output = io.StringIO()
        call_command('collect_gold_prices', stdout=output)
        collect.assert_called_once()
        self.assertIn('already claimed', output.getvalue())
