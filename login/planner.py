import calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .importers.services import import_transactions
from .models import MoneyAccount, RecurringPayment, Transaction, UserProfile


def next_month(due: date, day: int) -> date:
    month = due.month + 1
    year = due.year
    if month == 13:
        month, year = 1, year + 1
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def payment_calendar(payments, month_start: date):
    end_year, end_month = (month_start.year + 1, 1) if month_start.month == 12 else (month_start.year, month_start.month + 1)
    month_end = date(end_year, end_month, 1) - timedelta(days=1)
    due_by_day = defaultdict(list)
    for item in payments:
        if not item.active:
            continue
        due = item.next_due
        while due <= month_end:
            if due >= month_start:
                due_by_day[due].append(item)
            due = next_month(due, item.day_of_month)
    return [[{'date': day, 'in_month': day.month == month_start.month, 'items': due_by_day[day]}
             for day in week] for week in calendar.Calendar().monthdatescalendar(month_start.year, month_start.month)]


def positive_amount(raw):
    try:
        amount = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Enter a valid amount.')
    if not amount.is_finite() or amount <= 0 or amount > Decimal('9999999999.99'):
        raise ValueError('Enter an amount greater than zero.')
    return amount.quantize(Decimal('0.01'))


def account_for_user(user, raw):
    if not raw:
        return None
    return get_object_or_404(MoneyAccount, pk=raw, user=user)


def record_due_payment(item: RecurringPayment, today: date, use_due_date: bool = False) -> None:
    with transaction.atomic():
        item = RecurringPayment.objects.select_for_update().get(pk=item.pk, user=item.user)
        if not item.active or item.next_due > today:
            raise ValueError('This payment is not due yet.')
        if item.last_recorded_due == item.next_due:
            raise ValueError('This payment was already recorded.')
        Transaction.objects.create(
            user=item.user, account=item.account, title=item.name,
            amount=item.amount, txn_type='expense', category=item.category,
            date=item.next_due if use_due_date else today,
            note=f'Recurring payment due {item.next_due.isoformat()}',
        )
        item.last_recorded_due = item.next_due
        item.next_due = next_month(item.next_due, item.day_of_month)
        item.save(update_fields=['last_recorded_due', 'next_due'])


def record_automatic_payments(user, today: date) -> None:
    for item in RecurringPayment.objects.filter(user=user, active=True, auto_record=True, next_due__lte=today):
        while item.next_due <= today:
            record_due_payment(item, today, use_due_date=True)
            item.refresh_from_db(fields=['next_due'])


@login_required(login_url='/login/')
@require_http_methods(['GET', 'POST'])
def planner(request: HttpRequest) -> HttpResponse:
    today = timezone.localdate()
    record_automatic_payments(request.user, today)
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'add_account':
                name = request.POST.get('name', '').strip()[:60]
                kind = request.POST.get('kind', '')
                if not name or kind not in dict(MoneyAccount.KIND_CHOICES):
                    raise ValueError('Enter an account name and type.')
                opening = Decimal(request.POST.get('opening_balance') or '0')
                if not opening.is_finite():
                    raise ValueError('Enter a valid opening balance.')
                MoneyAccount.objects.create(user=request.user, name=name, kind=kind, opening_balance=opening)
                messages.success(request, 'Account added.')
            elif action == 'reminders':
                profile, _ = UserProfile.objects.get_or_create(user=request.user)
                profile.reminders_enabled = request.POST.get('enabled') == 'on'
                profile.save(update_fields=['reminders_enabled'])
                messages.success(request, 'Reminder preference saved.')
            elif action == 'add_recurring':
                name = request.POST.get('name', '').strip()[:120]
                kind = request.POST.get('kind', '')
                category = request.POST.get('category', 'other')
                due = date.fromisoformat(request.POST.get('next_due', ''))
                if not name or kind not in dict(RecurringPayment.KIND_CHOICES):
                    raise ValueError('Enter a bill or subscription name and type.')
                if category not in dict(Transaction.CATEGORY_CHOICES):
                    raise ValueError('Choose a valid category.')
                RecurringPayment.objects.create(
                    user=request.user, name=name, kind=kind,
                    amount=positive_amount(request.POST.get('amount')),
                    category=category, account=account_for_user(request.user, request.POST.get('account')),
                    next_due=due, day_of_month=due.day,
                    auto_record=request.POST.get('auto_record') == 'on',
                )
                messages.success(request, 'Recurring payment added.')
            elif action in ('record', 'toggle', 'delete'):
                item = get_object_or_404(RecurringPayment, pk=request.POST.get('id'), user=request.user)
                if action == 'record':
                    record_due_payment(item, today)
                    messages.success(request, 'Payment recorded and next due date updated.')
                elif action == 'toggle':
                    item.active = not item.active
                    item.save(update_fields=['active'])
                else:
                    item.delete()
                    messages.success(request, 'Recurring payment removed.')
            elif action == 'import':
                uploaded = request.FILES.get('file')
                if not uploaded or uploaded.size > 10 * 1024 * 1024:
                    raise ValueError('Choose a CSV or XLSX file under 10 MB.')
                result = import_transactions(request.user, uploaded)
                messages.success(request, f"Imported {result['imported']} transactions; skipped {result['skipped']} duplicates.")
            else:
                raise ValueError('Unknown action.')
        except (ValueError, InvalidOperation) as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            # Database uniqueness and malformed uploads should not break the page.
            messages.error(request, 'Could not save this item. Check the details and try again.')
        return redirect('planner')

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    accounts = list(MoneyAccount.objects.filter(user=request.user))
    totals = defaultdict(lambda: Decimal('0'))
    for row in Transaction.objects.filter(user=request.user, account__isnull=False).values('account_id', 'txn_type').annotate(total=Sum('amount')):
        totals[row['account_id']] += row['total'] if row['txn_type'] == 'income' else -row['total']
    for account in accounts:
        account.current_balance = account.opening_balance + totals[account.id]

    payments = list(RecurringPayment.objects.filter(user=request.user))
    upcoming = [item for item in payments if item.active and item.next_due <= today + timedelta(days=7)]
    month_start = today.replace(day=1)
    month_param = request.GET.get('month', '')
    if month_param:
        try:
            selected = date.fromisoformat(month_param + '-01')
            if abs(selected.year - today.year) > 5:
                raise ValueError
            month_start = selected
        except ValueError:
            month_start = today.replace(day=1)
    end_year, end_month = (month_start.year + 1, 1) if month_start.month == 12 else (month_start.year, month_start.month + 1)
    weeks = payment_calendar(payments, month_start)

    recent_start = today - timedelta(days=30)
    prior_start = today - timedelta(days=120)
    recent_spend = Transaction.objects.filter(user=request.user, txn_type='expense', date__gte=recent_start).aggregate(v=Sum('amount'))['v'] or Decimal('0')
    prior_spend = Transaction.objects.filter(user=request.user, txn_type='expense', date__gte=prior_start, date__lt=recent_start).aggregate(v=Sum('amount'))['v'] or Decimal('0')
    unusual = prior_spend > 0 and recent_spend > prior_spend / 3 * Decimal('1.5')
    current_month_start = today.replace(day=1)
    month_spend = Transaction.objects.filter(user=request.user, txn_type='expense', date__gte=current_month_start, date__lte=today).aggregate(v=Sum('amount'))['v'] or Decimal('0')
    budget_alert = bool(profile.salary and profile.salary > 0 and month_spend >= profile.salary * Decimal('0.8'))
    return render(request, 'login/planner.html', {
        'profile': profile, 'active_nav': 'planner', 'accounts': accounts,
        'payments': payments, 'upcoming': upcoming,
        'calendar_weeks': weeks, 'today': today, 'month_label': month_start.strftime('%B %Y'),
        'previous_month': (month_start - timedelta(days=1)).strftime('%Y-%m'),
        'next_month': date(end_year, end_month, 1).strftime('%Y-%m'),
        'categories': Transaction.CATEGORY_CHOICES, 'unusual_spending': unusual,
        'recent_spend': recent_spend, 'prior_monthly_average': prior_spend / 3,
        'budget_alert': budget_alert, 'month_spend': month_spend,
    })
