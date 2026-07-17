import json
from datetime import date
from decimal import Decimal

from django.core import mail
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SavingsGoal, Transaction, UserProfile


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
        self.assertIn('saving_message', payload)
        self.assertTrue(payload['saving_message'])

    def test_chatbot_style_expense_uses_today_and_updates_salary_based_savings(self):
        response = self.client.post(
            reverse('api_add_transaction'),
            data=json.dumps({
                'title': 'Lunch',
                'amount': 250,
                'txn_type': 'expense',
                'category': 'food',
                'date': str(date.today()),
            }),
            content_type='application/json',
        )

        payload = response.json()
        transaction = Transaction.objects.get(title='Lunch')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(transaction.date, date.today())
        self.assertEqual(transaction.amount, Decimal('250.00'))
        self.assertEqual(payload['total_saved'], 9750.0)
        self.assertIn('₹9,750', payload['saving_message'])


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
)
class SavingsGoalAllocationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='goals@example.com',
            email='goals@example.com',
            password='secret123',
            first_name='Goalie',
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            salary=Decimal('50000.00'),
            target_savings=Decimal('10000.00'),
        )
        self.client.force_login(self.user)

    def test_completed_auto_allocated_goal_is_capped_and_frozen(self):
        current_month = date.today().replace(day=1).strftime('%Y-%m')
        goal = SavingsGoal.objects.create(
            user=self.user,
            name='Emergency Fund',
            target_amount=Decimal('10000.00'),
            saved_amount=Decimal('0.00'),
            current_month_auto_allocation=Decimal('10000.00'),
            last_allocated_month=current_month,
            allocation_percentage=70,
            is_active=True,
        )

        response = self.client.get(reverse('savings'))
        goal.refresh_from_db()
        rendered_goal = response.context['goals'][0]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(goal.saved_amount, Decimal('10000.00'))
        self.assertEqual(goal.current_month_auto_allocation, Decimal('0.00'))
        self.assertFalse(goal.is_active)
        self.assertEqual(rendered_goal['saved_amount'], 10000.0)
        self.assertEqual(rendered_goal['progress_pct'], 100)
        self.assertTrue(rendered_goal['is_complete'])
        self.assertFalse(rendered_goal['is_active'])

    def test_completed_goals_are_excluded_from_future_allocation(self):
        completed = SavingsGoal.objects.create(
            user=self.user,
            name='Done Goal',
            target_amount=Decimal('10000.00'),
            saved_amount=Decimal('10000.00'),
            current_month_auto_allocation=Decimal('0.00'),
            allocation_percentage=70,
            is_active=False,
        )
        active = SavingsGoal.objects.create(
            user=self.user,
            name='Next Goal',
            target_amount=Decimal('20000.00'),
            saved_amount=Decimal('0.00'),
            current_month_auto_allocation=Decimal('0.00'),
            allocation_percentage=50,
            is_active=True,
        )

        response = self.client.get(reverse('api_goal_allocations'))
        payload = response.json()
        allocations = {item['id']: item for item in payload['allocations']}

        self.assertEqual(response.status_code, 200)
        self.assertEqual(allocations[completed.id]['allocated_this_month'], 0)
        self.assertEqual(allocations[completed.id]['saved_amount'], 10000.0)
        self.assertTrue(allocations[completed.id]['is_complete'])
        self.assertGreater(allocations[active.id]['allocated_this_month'], 0)


class MonthlyAnalysisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='monthly@example.com',
            email='monthly@example.com',
            password='secret123',
            first_name='Monthy',
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            salary=Decimal('12000.00'),
            target_savings=Decimal('5000.00'),
        )
        self.client.force_login(self.user)

    def test_monthly_page_uses_real_month_data(self):
        Transaction.objects.bulk_create([
            Transaction(
                user=self.user,
                title='Salary Credit',
                amount=Decimal('3000.00'),
                txn_type='income',
                category='other',
                date=date(2026, 5, 2),
            ),
            Transaction(
                user=self.user,
                title='Rent',
                amount=Decimal('2500.00'),
                txn_type='expense',
                category='rent',
                date=date(2026, 5, 3),
            ),
            Transaction(
                user=self.user,
                title='Groceries',
                amount=Decimal('700.00'),
                txn_type='expense',
                category='groceries',
                date=date(2026, 5, 10),
            ),
            Transaction(
                user=self.user,
                title='Transport',
                amount=Decimal('300.00'),
                txn_type='expense',
                category='transport',
                date=date(2026, 5, 18),
            ),
        ])

        response = self.client.get(reverse('monthly'), {'month': '2026-05'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_month_param'], '2026-05')
        self.assertEqual(response.context['selected_month_label'], 'May 2026')
        self.assertEqual(response.context['total_expense'], Decimal('3500.00'))
        self.assertEqual(response.context['total_balance'], Decimal('8500.00'))
        self.assertEqual(response.context['categories'][0]['label'], 'Rent')
        self.assertEqual(response.context['donut_legend'][0]['label'], 'Rent')
        self.assertGreaterEqual(len(response.context['weekly_chart']['weeks']), 4)
        self.assertEqual(response.context['top_spending_days'][0]['label'], 'May 03')
        self.assertGreater(response.context['monthly_score']['value'], 0)

    def test_email_monthly_analysis_sends_same_month_summary(self):
        Transaction.objects.bulk_create([
            Transaction(
                user=self.user,
                title='Rent',
                amount=Decimal('2500.00'),
                txn_type='expense',
                category='rent',
                date=date(2026, 5, 3),
            ),
            Transaction(
                user=self.user,
                title='Groceries',
                amount=Decimal('700.00'),
                txn_type='expense',
                category='groceries',
                date=date(2026, 5, 10),
            ),
        ])

        response = self.client.post(
            f"{reverse('api_email_monthly_analysis')}?month=2026-05",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['monthly@example.com'])
        self.assertIn('May 2026', mail.outbox[0].subject)
        self.assertIn('Rent', mail.outbox[0].body)
        self.assertIn('₹3,200.00', mail.outbox[0].body)
