import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Transaction, UserProfile


class DashboardInsightsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='mani@example.com',
            email='mani@example.com',
            password='secret123',
            first_name='Mani',
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            salary=Decimal('10000.00'),
            target_savings=Decimal('6000.00'),
        )
        self.client.force_login(self.user)

    def test_dashboard_context_uses_live_category_breakdown_for_insights(self):
        Transaction.objects.bulk_create([
            Transaction(
                user=self.user,
                title='House Rent',
                amount=Decimal('3000.00'),
                txn_type='expense',
                category='rent',
                date=date.today(),
            ),
            Transaction(
                user=self.user,
                title='Groceries Run',
                amount=Decimal('1200.00'),
                txn_type='expense',
                category='groceries',
                date=date.today(),
            ),
            Transaction(
                user=self.user,
                title='Movie Night',
                amount=Decimal('800.00'),
                txn_type='expense',
                category='entertainment',
                date=date.today(),
            ),
        ])

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['insight_total'], Decimal('5000.00'))
        self.assertEqual(len(response.context['insight_segments']), 3)
        self.assertEqual(response.context['cat_tiles'][0]['label'], 'Rent')
        self.assertEqual(response.context['insight_segments'][0]['dashoffset'], 0)
        self.assertIn('"label": "Rent"', response.context['insight_segments_json'])

    def test_add_transaction_api_returns_dynamic_insight_payload(self):
        Transaction.objects.create(
            user=self.user,
            title='Initial Rent',
            amount=Decimal('1500.00'),
            txn_type='expense',
            category='rent',
            date=date.today(),
        )

        response = self.client.post(
            reverse('api_add_transaction'),
            data=json.dumps({
                'title': 'Dinner',
                'amount': 900,
                'txn_type': 'expense',
                'category': 'food',
                'date': str(date.today()),
            }),
            content_type='application/json',
        )
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['insight_total'], 2400.0)
        self.assertEqual(payload['cat_tiles'][0]['label'], 'Rent')
        self.assertEqual(payload['cat_tiles'][1]['label'], 'Food')
        self.assertEqual(len(payload['insight_segments']), 2)
        self.assertIn('coach', payload)
