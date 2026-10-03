import json
import re
from unittest.mock import patch
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core import mail
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from .models import (
    MonthlyAnalysisMailSetting,
    OfficeBalance,
    OfficeEntry,
    OfficeHiddenSuggestion,
    PageView,
    SavingsGoal,
    Transaction,
    UserProfile,
)
from .templatetags.office_currency import office_currency, office_currency_plus


class SignupOtpTests(TestCase):
    def test_signup_sends_otp_and_waits_for_verification(self):
        response = self.client.post(
            reverse('signup'),
            {
                'name': 'Mani Gururam',
                'email': 'newuser@example.com',
                'password': 'StrongPass123!',
                'confirm_password': 'StrongPass123!',
            },
        )

        self.assertRedirects(response, reverse('signup_verify'))
        user = User.objects.get(email='newuser@example.com')
        profile = UserProfile.objects.get(user=user)
        self.assertFalse(user.is_active)
        self.assertFalse(profile.email_is_verified)
        self.assertRegex(profile.email_verification_code, r'^\d{4}$')
        self.assertEqual(self.client.session['pending_signup_user_id'], user.id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['newuser@example.com'])
        self.assertIn(profile.email_verification_code, mail.outbox[0].body)

    def test_signup_verify_activates_user_and_logs_in(self):
        user = User.objects.create_user(
            username='verify@example.com',
            email='verify@example.com',
            password='StrongPass123!',
            first_name='Verify',
            is_active=False,
        )
        profile = UserProfile.objects.get(user=user)
        code = '1234'
        profile.email_verification_code = code
        profile.email_verification_sent_at = timezone.now()
        profile.email_is_verified = False
        profile.save()
        session = self.client.session
        session['pending_signup_user_id'] = user.id
        session.save()

        response = self.client.post(reverse('signup_verify'), {'otp': code})

        self.assertRedirects(response, reverse('dashboard'))
        user.refresh_from_db()
        profile.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(profile.email_is_verified)
        self.assertEqual(profile.email_verification_code, '')
        self.assertNotIn('pending_signup_user_id', self.client.session)


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='login@example.com',
            email='login@example.com',
            password='StrongPass123!',
            first_name='Login',
        )
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.email_is_verified = True
        self.profile.save(update_fields=['email_is_verified'])

    def test_password_login_still_works(self):
        response = self.client.post(
            reverse('login'),
            {
                'email': 'login@example.com',
                'password': 'StrongPass123!',
            },
        )

        self.assertRedirects(response, reverse('dashboard'))


class InvitationSetupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='invited@example.com',
            email='invited@example.com',
            password='TemporaryPass123!',
        )
        self.profile = UserProfile.objects.get(user=self.user)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_invited_user_completes_otp_and_profile_setup_before_login(self):
        response = self.client.post(
            reverse('login'),
            {'email': 'invited@example.com', 'password': 'TemporaryPass123!'},
        )

        self.assertRedirects(response, reverse('invitation_verify'))
        self.profile.refresh_from_db()
        self.assertRegex(self.profile.email_verification_code, r'^\d{4}$')
        self.assertEqual(len(mail.outbox), 1)

        response = self.client.post(
            reverse('invitation_verify'),
            {'otp': self.profile.email_verification_code},
        )

        self.assertRedirects(response, reverse('invitation_setup'))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.email_is_verified)

        response = self.client.post(
            reverse('invitation_setup'),
            {
                'name': 'Invited User',
                'password': 'MyNewPass123!',
                'confirm_password': 'MyNewPass123!',
                'currency': 'usd',
            },
        )

        self.assertRedirects(response, reverse('dashboard'))
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Invited')
        self.assertEqual(self.user.last_name, 'User')
        self.assertTrue(self.user.check_password('MyNewPass123!'))
        self.assertEqual(self.profile.currency, 'usd')

        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'data-currency="usd"')


class PwaCsrfCacheTests(TestCase):
    def test_auth_pages_are_never_cached(self):
        for route_name in ('signup', 'signup_verify', 'login'):
            response = self.client.get(reverse(route_name))
            self.assertIn('no-store', response.headers.get('Cache-Control', ''))

    def test_service_worker_does_not_cache_auth_navigations(self):
        response = self.client.get(reverse('service_worker'))
        content = response.content.decode()

        self.assertContains(response, "spendwise-shell-v5")
        self.assertIn("request.mode === 'navigate'", content)
        self.assertIn("event.respondWith(fetch(request));", content)
        self.assertNotIn("cache.addAll(SHELL_ASSETS)", content)


class MonthlyAnalysisMailAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin@example.com',
            email='admin@example.com',
            password='StrongPass123!',
        )
        self.client.force_login(self.admin_user)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
    def test_send_now_admin_button_triggers_batch_sender(self):
        url = reverse('admin:login_monthlyanalysismailsetting_send_now')
        current_month = timezone.localtime().strftime('%Y-%m')
        with patch('login.admin.send_monthly_analysis_batch') as sender:
            sender.return_value = {
                'month': current_month,
                'sent': 2,
                'failed': 0,
                'failures': [],
            }
            response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        sender.assert_called_once_with(current_month)
        self.assertContains(response, 'Sent 2 monthly analysis email')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_send_now_admin_button_warns_when_smtp_is_not_configured(self):
        url = reverse('admin:login_monthlyanalysismailsetting_send_now')
        with patch('login.admin.send_monthly_analysis_batch') as sender:
            response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        sender.assert_not_called()
        self.assertContains(response, 'SMTP is not configured')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
    def test_send_now_respects_disabled_setting(self):
        MonthlyAnalysisMailSetting.objects.create(pk=1, enabled=False)
        url = reverse('admin:login_monthlyanalysismailsetting_send_now')
        with patch('login.admin.send_monthly_analysis_batch') as sender:
            sender.return_value = {'month': '2026-09', 'sent': 2, 'failed': 0, 'failures': []}
            response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        sender.assert_called_once()
        self.assertContains(response, 'Sent 2 monthly analysis email')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
    def test_send_now_allows_resending_monthly_emails(self):
        current_month = timezone.localtime().strftime('%Y-%m')
        MonthlyAnalysisMailSetting.objects.create(pk=1, last_sent_month=current_month)
        url = reverse('admin:login_monthlyanalysismailsetting_send_now')
        with patch('login.admin.send_monthly_analysis_batch') as sender:
            sender.return_value = {'month': current_month, 'sent': 2, 'failed': 0, 'failures': []}
            response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        sender.assert_called_once()
        self.assertContains(response, 'Sent 2 monthly analysis email')

    def test_schedule_page_creates_a_single_editable_schedule(self):
        response = self.client.get(
            reverse('admin:login_monthlyanalysismailsetting_changelist')
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(MonthlyAnalysisMailSetting.objects.count(), 1)
        self.assertContains(response, 'Send report now')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
    def test_send_to_one_user_sends_the_selected_report(self):
        user = User.objects.create_user(
            username='report@example.com',
            email='report@example.com',
            password='StrongPass123!',
        )
        url = reverse('admin:login_monthlyanalysismailsetting_send_to_user')

        with patch('login.admin.send_monthly_analysis_email') as sender:
            response = self.client.post(url, {
                'recipient': str(user.pk),
                'start_date': '2026-08-01',
                'end_date': '2026-08-31',
            }, follow=True)

        self.assertEqual(response.status_code, 200)
        sender.assert_called_once_with(
            user,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
        )
        self.assertContains(response, 'sent to report@example.com')


class MonthlyAnalysisMailCommandTests(TestCase):
    @patch('login.management.commands.send_monthly_analysis_emails.send_monthly_analysis_batch')
    @patch('login.management.commands.send_monthly_analysis_emails.timezone.localtime')
    def test_scheduled_delivery_sends_previous_completed_month(self, localtime, sender):
        MonthlyAnalysisMailSetting.objects.create(
            pk=1,
            enabled=True,
            send_day=1,
            send_time=datetime.strptime('09:00', '%H:%M').time(),
        )
        localtime.return_value = timezone.make_aware(datetime(2026, 9, 1, 10, 0))
        sender.return_value = {'month': '2026-08', 'sent': 1, 'failed': 0, 'failures': []}

        from django.core.management import call_command
        call_command('send_monthly_analysis_emails')

        sender.assert_called_once_with('2026-08')


class AdminToolAccessTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff@example.com',
            email='staff@example.com',
            password='StrongPass123!',
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            username='superuser@example.com',
            email='superuser@example.com',
            password='StrongPass123!',
        )

    def test_staff_user_cannot_access_sensitive_admin_tools(self):
        self.client.force_login(self.staff_user)

        for route_name in ('admin_dashboard', 'admin_broadcast'):
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 302)
            self.assertIn('/admin/login/', response.url)

    def test_superuser_can_access_sensitive_admin_tools(self):
        self.client.force_login(self.superuser)

        for route_name in ('admin_dashboard', 'admin_broadcast'):
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200)

    def test_admin_home_has_a_separate_manual_user_option(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('admin:index'))

        self.assertContains(response, 'Manually Add User')
        self.assertContains(response, reverse('admin:auth_user_add'))

    def test_users_page_has_a_manual_add_user_button(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('admin:auth_user_changelist'))

        self.assertContains(response, 'Manually Add User')
        self.assertContains(response, reverse('admin:auth_user_add'))

    def test_admin_sidebar_has_an_invite_user_link(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('admin:auth_user_changelist'))

        self.assertContains(response, 'Invite User')
        self.assertContains(response, reverse('admin:auth_user_add'))

    def test_analytics_lists_recently_active_users_below_the_charts(self):
        customer = User.objects.create_user(
            username='active@example.com',
            email='active@example.com',
            password='StrongPass123!',
            first_name='Active',
        )
        PageView.objects.create(user=customer, path='/dashboard/', view_count=3)
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertContains(response, 'Recently Active Users')
        self.assertContains(response, 'active@example.com')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
    def test_broadcast_handles_email_service_failure(self):
        recipient = User.objects.create_user(
            username='recipient@example.com',
            email='recipient@example.com',
            password='StrongPass123!',
        )
        self.client.force_login(self.superuser)

        with patch('login.admin_views.EmailMessage.send', side_effect=OSError('SMTP unavailable')):
            response = self.client.post(
                reverse('admin_broadcast'),
                {'subject': 'Maintenance', 'message': 'Scheduled maintenance tonight.'},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The broadcast could not be sent')


class ManualUserAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin@example.com',
            email='admin@example.com',
            password='StrongPass123!',
        )
        self.client.force_login(self.admin_user)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_manually_created_user_receives_login_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('admin:auth_user_add'),
                {
                    'email': 'newuser@example.com',
                    '_save': 'Save',
                },
            )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='newuser@example.com')
        self.assertEqual(user.username, 'newuser@example.com')
        self.assertTrue(user.is_active)
        self.assertFalse(user.profile.email_is_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['newuser@example.com'])
        self.assertIn('Temporary password:', mail.outbox[0].body)
        self.assertIn('After signing in, verify your email with a 4-digit OTP', mail.outbox[0].body)
        self.assertEqual(len(mail.outbox[0].alternatives), 1)
        self.assertIn('Welcome to SpendWise', mail.outbox[0].alternatives[0].content)
        self.assertIn('Sign In to SpendWise', mail.outbox[0].alternatives[0].content)

    def test_users_list_has_row_and_bulk_delete_controls(self):
        user = User.objects.create_user(
            username='remove@example.com',
            email='remove@example.com',
            password='StrongPass123!',
        )

        response = self.client.get(reverse('admin:auth_user_changelist'))

        self.assertContains(response, reverse('admin:auth_user_delete', args=[user.pk]))
        self.assertContains(response, 'Delete selected')

    def test_selected_user_delete_requires_confirmation(self):
        user = User.objects.create_user(
            username='confirm-remove@example.com',
            email='confirm-remove@example.com',
            password='StrongPass123!',
        )

        response = self.client.post(
            reverse('admin:auth_user_changelist'),
            {
                'action': 'delete_selected',
                '_selected_action': str(user.pk),
                'index': '0',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Are you sure you want to delete')
        self.assertTrue(User.objects.filter(pk=user.pk).exists())


class DashboardInsightsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='mani@example.com',
            email='mani@example.com',
            password='secret123',
            first_name='Mani',
        )
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.salary = Decimal('10000.00')
        self.profile.target_savings = Decimal('6000.00')
        self.profile.save(update_fields=['salary', 'target_savings'])
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

    def test_lend_expense_can_be_marked_paid_to_restore_available_salary(self):
        response = self.client.post(
            reverse('api_add_transaction'),
            data=json.dumps({
                'title': 'Lent to friend',
                'amount': 2000,
                'txn_type': 'expense',
                'category': 'lend',
                'date': str(date.today()),
            }),
            content_type='application/json',
        )
        payload = response.json()
        txn = Transaction.objects.get(title='Lent to friend')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['total_expense'], 2000.0)
        self.assertEqual(payload['total_saved'], 8000.0)
        self.assertFalse(txn.is_settled)

        paid_response = self.client.post(reverse('api_mark_lend_paid', args=[txn.id]))
        paid_payload = paid_response.json()
        txn.refresh_from_db()

        self.assertEqual(paid_response.status_code, 200)
        self.assertTrue(txn.is_settled)
        self.assertEqual(paid_payload['total_expense'], 0.0)
        self.assertEqual(paid_payload['total_saved'], 10000.0)
        self.assertTrue(paid_payload['txn']['is_settled'])

    def test_lend_tracker_page_separates_pending_and_paid_lends(self):
        Transaction.objects.create(
            user=self.user,
            title='Pending lend',
            amount=Decimal('1200.00'),
            txn_type='expense',
            category='lend',
            date=date.today(),
        )
        Transaction.objects.create(
            user=self.user,
            title='Paid lend',
            amount=Decimal('700.00'),
            txn_type='expense',
            category='lend',
            is_settled=True,
            date=date.today(),
        )

        response = self.client.get(reverse('lend'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_nav'], 'lend')
        self.assertEqual(response.context['pending_total'], Decimal('1200.00'))
        self.assertEqual(response.context['paid_total'], Decimal('700.00'))
        self.assertContains(response, 'Pending lend')
        self.assertContains(response, 'Paid lend')
        self.assertContains(response, 'id="lendModal"')
        self.assertContains(response, "category: 'lend'")

    def test_lend_tracker_can_create_lend_transaction(self):
        response = self.client.post(
            reverse('api_add_transaction'),
            data=json.dumps({
                'title': 'Lend from tracker',
                'amount': 500,
                'txn_type': 'expense',
                'category': 'lend',
                'date': str(date.today()),
            }),
            content_type='application/json',
        )

        txn = Transaction.objects.get(title='Lend from tracker')
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(txn.category, 'lend')
        self.assertFalse(txn.is_settled)
        self.assertEqual(payload['total_expense'], 500.0)

    def test_lend_transaction_requires_person_or_note(self):
        response = self.client.post(
            reverse('api_add_transaction'),
            data=json.dumps({
                'title': '',
                'amount': 500,
                'txn_type': 'expense',
                'category': 'lend',
                'date': str(date.today()),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Person or note is required', response.json()['error'])
        self.assertFalse(Transaction.objects.filter(category='lend').exists())

    def test_lend_transaction_rejects_future_date(self):
        response = self.client.post(
            reverse('api_add_transaction'),
            data=json.dumps({
                'title': 'Future lend',
                'amount': 500,
                'txn_type': 'expense',
                'category': 'lend',
                'date': str(date.today() + timedelta(days=1)),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('future', response.json()['error'])
        self.assertFalse(Transaction.objects.filter(title='Future lend').exists())


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
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.salary = Decimal('50000.00')
        self.profile.target_savings = Decimal('10000.00')
        self.profile.save(update_fields=['salary', 'target_savings'])
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
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.salary = Decimal('12000.00')
        self.profile.target_savings = Decimal('5000.00')
        self.profile.save(update_fields=['salary', 'target_savings'])
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


class OfficeMoneyFlowTests(TestCase):
    """The office tracker is a standalone flow: opening balance + came - taken."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='office@example.com',
            email='office@example.com',
            password='secret123',
        )
        self.client.force_login(self.user)

    def _add(self, **payload):
        return self.client.post(
            reverse('api_office_add_entry'),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_balance_change_recalculates_total_without_changing_entries(self):
        self.client.post(
            reverse('api_office_set_balance'),
            data=json.dumps({'amount': '100'}),
            content_type='application/json',
        )
        self._add(direction='came', name='Ravi', amount='50')
        entry = OfficeEntry.objects.get(user=self.user)

        response = self.client.post(
            reverse('api_office_set_balance'),
            data=json.dumps({'amount': '200'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], '250.00')
        entry.refresh_from_db()
        self.assertEqual(entry.amount, Decimal('50'))
        self.assertEqual(entry.name, 'Ravi')
        self.assertEqual(OfficeEntry.objects.filter(user=self.user).count(), 1)

    def test_office_cents_and_missing_balance_request(self):
        balance_url = reverse('api_office_set_balance')
        saved = self.client.post(
            balance_url, data=json.dumps({'amount': '0.10'}),
            content_type='application/json',
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self._add(direction='came', amount='0.20').json()['total'], '0.30')
        self.assertEqual(self._add(direction='taken', amount='0.03').json()['total'], '0.27')
        self.assertIn('₹0.27', self.client.get(reverse('office')).content.decode())

        missing = self.client.post(balance_url, data='{}', content_type='application/json')
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(OfficeBalance.objects.get(user=self.user).amount, Decimal('0.10'))

    def test_office_display_keeps_large_totals_to_the_cent(self):
        self.assertEqual(
            office_currency(Decimal('100000000000000.01')),
            '₹10,00,00,00,00,00,000.01',
        )
        self.assertEqual(office_currency_plus(Decimal('0.20')), '+₹0.20')

    def test_office_back_link_and_balance_controls_are_self_contained(self):
        page = self.client.get(reverse('office')).content.decode()
        for target in ('officeOverview', 'officeEntry', 'officeHistorySection'):
            self.assertIn(f'id="{target}"', page)
        self.assertIn('aria-label="Back to SpendWise"', page)
        self.assertNotIn('class="office-sidebar"', page)
        self.assertNotIn('officeBalanceNotice', page)
        self.assertIn('id="officeBalanceSave"', page)
        # The starting balance previews as you type, but only Save Balance
        # (or Enter) actually persists it.
        self.assertIn('previewOpening', page)
        self.assertIn("openingInput.addEventListener('input', previewOpening)", page)
        self.assertIn('<dialog class="office-confirm-dialog office-balance-dialog" id="officeBalanceConfirm"', page)
        self.assertIn('Current starting', page)
        self.assertIn('New starting', page)
        self.assertIn('Projected current balance', page)
        self.assertIn('Your existing entries and dates stay the same.', page)
        self.assertIn('dialog.showModal()', page)
        self.assertIn('id="officeDeleteConfirm"', page)
        self.assertIn('id="officeDeleteName"', page)
        self.assertIn('You can undo the deletion for 10 seconds.', page)
        self.assertNotIn('scheduleOpeningSave', page)
        self.assertIn('href="/dashboard/"', page)

    def test_recent_entries_are_paginated_and_searchable(self):
        for i in range(28):
            OfficeEntry.objects.create(
                user=self.user, direction='came', amount=Decimal('10.00'),
                name='Needle' if i == 20 else f'Person {i}',
                entry_date=date.today() - timedelta(days=i),
            )
        first = self.client.get(reverse('office'))
        self.assertEqual(len(first.context['entries_page']), 8)
        self.assertEqual(first.context['entries_page'].paginator.count, 28)
        self.assertEqual(first.context['entries_page'][0].name, 'Person 0')

        last = self.client.get(reverse('office'), {'page': 4})
        self.assertEqual(len(last.context['entries_page']), 4)
        middle = self.client.get(reverse('office'), {'page': 2})
        self.assertEqual(middle.context['entries_page'][0].name, 'Person 8')

        found = self.client.get(reverse('office'), {'q': 'Needle'})
        self.assertEqual(found.context['entries_page'].paginator.count, 1)
        self.assertEqual(found.context['entries_page'][0].name, 'Needle')

    def test_deleted_entries_leave_history_but_can_be_restored(self):
        keep = self._add(direction='came', name='Visible', amount='100')
        self.assertEqual(keep.status_code, 200)
        entry = OfficeEntry.objects.get(user=self.user)

        removed = self.client.post(
            reverse('api_office_delete_entry', kwargs={'entry_id': entry.id}),
            data=json.dumps({}), content_type='application/json',
        )
        self.assertEqual(removed.status_code, 200)

        page = self.client.get(reverse('office'))
        self.assertEqual(page.context['entries_page'].paginator.count, 0)
        markup = page.content.decode()
        # The deleted entry leaves active history but remains available to restore.
        self.assertIn('id="officeDeleted"', markup)
        self.assertIn('Visible', markup)
        self.assertIn('class="office-restore">Restore</button>', markup)
        self.assertNotIn('class="office-history-row"', markup)
        # Totals still exclude it.
        self.assertEqual(page.context['office_total'], Decimal('0.00'))

    def test_recommendations_rank_most_used_names_first(self):
        for _ in range(3):
            self._add(direction='came', name='Ravi', amount='10')
        self._add(direction='came', name='Anita', amount='10')
        self._add(direction='came', name='Bala', amount='10')

        page = self.client.get(reverse('office'))
        self.assertEqual(page.context['name_suggestions'][0], 'Ravi')
        self.assertEqual(
            set(page.context['name_suggestions']),
            {'Ravi', 'Anita', 'Bala'},
        )
        markup = page.content.decode()
        # The dropdown under the name field keeps the suggestions. The
        # "Recent" chip row is gone.
        self.assertIn('id="officeNameSuggestions"', markup)
        self.assertIn('office-name-suggestions', markup)
        self.assertNotIn('office-name-recommend', markup)
        self.assertNotIn('office-name-chip', markup)

    def test_each_recommendation_can_be_removed_individually(self):
        self._add(direction='came', name='Ravi', amount='10')
        self._add(direction='came', name='Anita', amount='10')
        page = self.client.get(reverse('office'))
        self.assertEqual(
            list(page.context['name_suggestions']),
            ['Anita', 'Ravi'],  # both used once, alphabetical
        )

        # Case must not matter, and the entry itself is untouched.
        hide = self.client.post(
            reverse('api_office_hide_suggestion'),
            data=json.dumps({'name': 'rAVI'}), content_type='application/json',
        )
        self.assertEqual(hide.status_code, 200)
        self.assertTrue(OfficeEntry.objects.filter(name='Ravi').exists())

        after = self.client.get(reverse('office'))
        self.assertEqual(after.context['name_suggestions'], ['Anita'])
        # Gone from the payload the chips are built from, so it cannot reappear.
        # The entry itself is untouched and still shows in History.
        payload = re.search(
            r'id="officeNameSuggestions"[^>]*>(.*?)</script>',
            after.content.decode(), re.S,
        ).group(1)
        self.assertNotIn('Ravi', payload)
        self.assertIn('Ravi', after.content.decode())
        self.assertIn('class="office-edit"', after.content.decode())

    def test_dismissed_suggestion_is_saved_per_account(self):
        self._add(direction='came', name='Ravi', amount='25')
        hide = self.client.post(
            reverse('api_office_hide_suggestion'),
            data=json.dumps({'name': 'rAVI'}), content_type='application/json',
        )
        self.assertEqual(hide.status_code, 200)
        self.assertTrue(OfficeHiddenSuggestion.objects.filter(user=self.user, name_key='ravi').exists())
        self.assertNotIn('Ravi', self.client.get(reverse('office')).context['name_suggestions'])

        other = User.objects.create_user(username='other-office@example.com', password='secret123')
        OfficeEntry.objects.create(user=other, direction='came', amount=Decimal('10'), name='Ravi')
        self.client.force_login(other)
        self.assertIn('Ravi', self.client.get(reverse('office')).context['name_suggestions'])
        self.client.force_login(self.user)
        self._add(direction='came', name='Ravi', amount='5')
        self.assertNotIn('Ravi', self.client.get(reverse('office')).context['name_suggestions'])
        entry = OfficeEntry.objects.filter(user=self.user, name='Ravi').first()
        edit = self.client.post(
            reverse('api_office_edit_entry', kwargs={'entry_id': entry.id}),
            data=json.dumps({
                'direction': 'came', 'name': 'Ravi', 'amount': '5',
                'entry_date': date.today().isoformat(),
            }),
            content_type='application/json',
        )
        self.assertEqual(edit.status_code, 200)
        self.assertNotIn('Ravi', self.client.get(reverse('office')).context['name_suggestions'])

    def test_edit_delete_and_restore_preserve_entry(self):
        self._add(direction='came', name='Ravi', amount='50')
        entry = OfficeEntry.objects.get(user=self.user)
        edited_date = (date.today() - timedelta(days=2)).isoformat()
        edit = self.client.post(
            reverse('api_office_edit_entry', kwargs={'entry_id': entry.id}),
            data=json.dumps({'direction': 'taken', 'name': 'Office', 'amount': '30.00', 'entry_date': edited_date}),
            content_type='application/json',
        )
        self.assertEqual(edit.status_code, 200)
        self.assertEqual(edit.json()['total'], '-30.00')
        entry.refresh_from_db()
        self.assertEqual(entry.name, 'Office')
        self.assertEqual(entry.entry_date.isoformat(), edited_date)

        delete = self.client.post(reverse('api_office_delete_entry', kwargs={'entry_id': entry.id}))
        self.assertEqual(delete.status_code, 200)
        self.assertEqual(delete.json()['total'], '0.00')
        entry.refresh_from_db()
        self.assertIsNotNone(entry.deleted_at)
        # Soft-deleted rows stay out of the page, but the restore path still works.
        self.assertEqual(OfficeEntry.objects.filter(user=self.user, deleted_at__isnull=False).count(), 1)
        self.assertEqual(self.client.get(reverse('office')).context['entries_page'].paginator.count, 0)

        restore = self.client.post(reverse('api_office_restore_entry', kwargs={'entry_id': entry.id}))
        self.assertEqual(restore.status_code, 200)
        self.assertEqual(restore.json()['total'], '-30.00')
        entry.refresh_from_db()
        self.assertIsNone(entry.deleted_at)

    def test_edit_rejects_invalid_values_and_other_users(self):
        self._add(direction='came', name='Ravi', amount='50')
        entry = OfficeEntry.objects.get(user=self.user)
        edit_url = reverse('api_office_edit_entry', kwargs={'entry_id': entry.id})
        payload = {'direction': 'came', 'name': 'Ravi', 'entry_date': date.today().isoformat()}
        for bad_amount in ('NaN', '0', '1.234'):
            response = self.client.post(
                edit_url, data=json.dumps({**payload, 'amount': bad_amount}),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400)
        intruder = User.objects.create_user(username='intruder-edit@example.com', password='secret123')
        self.client.force_login(intruder)
        response = self.client.post(
            edit_url, data=json.dumps({**payload, 'amount': '20'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        entry.refresh_from_db()
        self.assertEqual(entry.amount, Decimal('50'))

    def test_search_finds_date_and_amount_but_ignores_deleted_entries(self):
        chosen_date = date.today() - timedelta(days=10)
        target = OfficeEntry.objects.create(
            user=self.user, direction='taken', name='Older item',
            amount=Decimal('432.10'), entry_date=chosen_date,
        )
        OfficeEntry.objects.create(
            user=self.user, direction='came', name='Current item',
            amount=Decimal('20.00'), entry_date=date.today(),
        )
        for query in ('432.10', chosen_date.isoformat()):
            page = self.client.get(reverse('office'), {'q': query})
            self.assertEqual(page.context['entries_page'].paginator.count, 1)
            self.assertEqual(page.context['entries_page'][0].id, target.id)
        self.client.post(reverse('api_office_delete_entry', kwargs={'entry_id': target.id}))
        page = self.client.get(reverse('office'), {'q': 'Older item'})
        self.assertEqual(page.context['entries_page'].paginator.count, 0)

    def test_deleted_entry_cannot_be_edited_or_deleted_twice(self):
        self._add(direction='came', name='Ravi', amount='50')
        entry = OfficeEntry.objects.get(user=self.user)
        delete_url = reverse('api_office_delete_entry', kwargs={'entry_id': entry.id})
        restore_url = reverse('api_office_restore_entry', kwargs={'entry_id': entry.id})
        edit_url = reverse('api_office_edit_entry', kwargs={'entry_id': entry.id})
        self.assertEqual(self.client.post(delete_url).status_code, 200)
        self.assertEqual(self.client.post(delete_url).status_code, 404)
        self.assertEqual(self.client.post(edit_url, data='{}', content_type='application/json').status_code, 404)
        self.assertEqual(self.client.post(restore_url).status_code, 200)
        self.assertEqual(self.client.post(restore_url).status_code, 404)

    def test_total_moves_with_coming_and_taken_entries(self):
        response = self.client.post(
            reverse('api_office_set_balance'),
            data=json.dumps({'amount': '1000'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], '1000.00')

        came = self._add(direction='came', name='Ravi', amount='500')
        self.assertEqual(came.status_code, 200)
        self.assertEqual(came.json()['total'], '1500.00')

        taken = self._add(direction='taken', name='Ravi', amount='250')
        self.assertEqual(taken.status_code, 200)
        self.assertEqual(taken.json()['total'], '1250.00')
        self.assertEqual(taken.json()['came_total'], '500.00')
        self.assertEqual(taken.json()['taken_total'], '250.00')

    def test_taken_can_drive_the_total_negative(self):
        self.client.post(
            reverse('api_office_set_balance'),
            data=json.dumps({'amount': '100'}),
            content_type='application/json',
        )
        response = self._add(direction='taken', name='Rent', amount='450')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], '-350.00')

        page = self.client.get(reverse('office')).content.decode()
        self.assertIn('is-negative', page)

    def test_office_entries_are_rejected_when_malformed(self):
        cases = [
            ({'direction': 'sideways', 'amount': '10'}, "Direction must be 'taken' or 'came'."),
            ({'direction': 'came', 'amount': '0'}, 'Amount must be greater than 0.'),
            ({'direction': 'came', 'amount': '-5'}, 'Amount must be greater than 0.'),
            ({'direction': 'came', 'amount': 'abc'}, 'Enter a valid amount.'),
            ({'direction': 'came', 'amount': '10', 'name': 'n' * 81}, 'Name must be 80 characters or less.'),
            ({'direction': 'came', 'amount': '10', 'entry_date': '2999-01-01'}, 'Date cannot be in the future.'),
            ({'direction': 'came', 'amount': '10', 'entry_date': 'not-a-date'}, 'Enter a valid date.'),
        ]
        for payload, expected in cases:
            with self.subTest(payload=payload):
                response = self._add(**payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['error'], expected)

        self.assertEqual(OfficeEntry.objects.count(), 0)

    def test_name_is_optional_and_back_dated_entries_keep_their_date(self):
        nameless = self._add(direction='came', amount='75')
        self.assertEqual(nameless.status_code, 200)
        self.assertEqual(nameless.json()['name'] if 'name' in nameless.json() else '', '')

        past = (date.today() - timedelta(days=3)).isoformat()
        dated = self._add(direction='taken', name='Ravi', amount='25', entry_date=past)
        self.assertEqual(dated.status_code, 200)
        self.assertEqual(dated.json()['entry_date'], past)

        page = self.client.get(reverse('office')).content.decode()
        self.assertIn('No name', page)

    def test_office_stays_separate_from_spendwise_with_back_navigation(self):
        self.client.post(
            reverse('api_office_set_balance'),
            data=json.dumps({'amount': '500'}),
            content_type='application/json',
        )
        self._add(direction='came', name='Ravi', amount='200')

        # Office money must not leak into the SpendWise transaction ledger.
        self.assertEqual(Transaction.objects.count(), 0)
        dashboard = self.client.get(reverse('dashboard')).content.decode()
        self.assertNotIn('Ravi', dashboard)

        # Office has a back link, while its ledger stays separate.
        office_page = self.client.get(reverse('office')).content.decode()
        self.assertIn('href="/dashboard/"', office_page)
        for url in ('monthly', 'lend', 'savings'):
            self.assertNotIn(f'href="/{url}/"', office_page)
        # ...while a normal page still shows all of them.
        for url in ('dashboard', 'monthly', 'lend', 'savings'):
            self.assertIn(f'href="/{url}/"', dashboard)
        self.assertIn('href="/office/"', dashboard)

    def test_entry_deletion_is_scoped_to_the_owner(self):
        self._add(direction='came', name='Ravi', amount='200')
        entry = OfficeEntry.objects.get(user=self.user)

        intruder = User.objects.create_user(
            username='intruder@example.com',
            email='intruder@example.com',
            password='secret123',
        )
        self.client.force_login(intruder)
        response = self.client.post(
            reverse('api_office_delete_entry', kwargs={'entry_id': entry.id}),
            data=json.dumps({}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(OfficeEntry.objects.filter(id=entry.id).exists())
