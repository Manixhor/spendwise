import json
import decimal
from datetime import date, timedelta
from decimal import Decimal
from math import ceil, pi

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from .models import Transaction, UserProfile, SavingsGoal
from .spending_coach import fetch_dad_joke, get_spending_message


# ── Helpers ───────────────────────────────────────────────
CATEGORY_ICONS = {
    'rent':          '🏠',
    'transport':     '🚗',
    'health':        '❤️',
    'groceries':     '🛒',
    'entertainment': '🎬',
    'shopping':      '🛍️',
    'food':          '🍽️',
    'utilities':     '💡',
    'other':         '📦',
}

CATEGORY_COLORS = {
    'rent':          '#67e8f9',
    'transport':     '#c4b5fd',
    'health':        '#bbf7d0',
    'groceries':     '#fde68a',
    'entertainment': '#fca5a5',
    'shopping':      '#fdba74',
    'food':          '#a5f3fc',
    'utilities':     '#d9f99d',
    'other':         '#e2e8f0',
}

CATEGORY_ACCENTS = {
    'rent':          {'bg': '#e0f7fa', 'fg': '#0097a7'},
    'transport':     {'bg': '#ede9ff', 'fg': '#7c3aed'},
    'health':        {'bg': '#dcfce7', 'fg': '#16a34a'},
    'groceries':     {'bg': '#fef9c3', 'fg': '#a16207'},
    'entertainment': {'bg': '#fee2e2', 'fg': '#dc2626'},
    'shopping':      {'bg': '#ffedd5', 'fg': '#c2410c'},
    'food':          {'bg': '#cffafe', 'fg': '#0891b2'},
    'utilities':     {'bg': '#ecfccb', 'fg': '#4d7c0f'},
    'other':         {'bg': '#e5e7eb', 'fg': '#475569'},
}

INSIGHTS_DONUT_CIRCUMFERENCE = round(2 * pi * 46, 1)
INSIGHTS_SEGMENT_LIMIT = 5
MONTHLY_SCORE_CIRCUMFERENCE = round(2 * pi * 40, 1)


def _serialize_category_tiles(cat_data):
    """Return category data sorted by highest spend for template/API usage."""
    sorted_items = sorted(
        cat_data.items(),
        key=lambda item: item[1]['amount'],
        reverse=True,
    )
    return [
        {
            'key': key,
            'label': value['label'],
            'amount': float(value['amount']),
            'icon': value['icon'],
            'color': value['color'],
        }
        for key, value in sorted_items
    ]


def _build_insight_segments(cat_tiles, total_expense):
    """Build SVG stroke data for the dashboard insights donut."""
    if total_expense <= 0:
        return []

    dash_offset = 0
    segments = []
    total_expense_float = float(total_expense)

    for tile in cat_tiles[:INSIGHTS_SEGMENT_LIMIT]:
        segment_size = round(
            INSIGHTS_DONUT_CIRCUMFERENCE * (tile['amount'] / total_expense_float),
            1,
        )
        segments.append({
            **tile,
            'dasharray': f'{segment_size} {round(max(INSIGHTS_DONUT_CIRCUMFERENCE - segment_size, 0), 1)}',
            'dashoffset': round(-dash_offset, 1),
            'share_pct': round(tile['amount'] / total_expense_float * 100, 1),
        })
        dash_offset += segment_size

    return segments


def _dashboard_stats_payload(stats):
    """Serialize dashboard stats for JSON responses."""
    return {
        'total_income': float(stats['total_income']),
        'total_expense': float(stats['total_expense']),
        'total_saved': float(stats['total_saved']),
        'total_balance': float(stats['total_balance']),
        'spend_pct': stats['spend_pct'],
        'savings_pct': stats['savings_pct'],
        'ring_dash': stats['ring_dash'],
        'ring_gap': stats['ring_gap'],
        'cat_tiles': stats['cat_tiles'],
        'insight_segments': stats['insight_segments'],
        'insight_total': float(stats['insight_total']),
        'insight_stock': stats['insight_stock'],
        'chart_months': stats['chart_months'],
        'coach': get_spending_message(stats['spend_pct']),
    }


def _add_months(month_start: date, delta: int) -> date:
    month_index = month_start.month - 1 + delta
    year = month_start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _month_bounds(month_start: date) -> tuple[date, date]:
    next_month = _add_months(month_start, 1)
    return month_start, next_month - timedelta(days=1)


def _parse_month_param(month_value: str | None) -> date:
    if month_value:
        try:
            year_str, month_str = month_value.split('-', 1)
            return date(int(year_str), int(month_str), 1)
        except (TypeError, ValueError):
            pass
    today = date.today()
    return today.replace(day=1)


def _format_axis_currency(value: float) -> str:
    if value >= 1000:
        display = value / 1000
        suffix = 'k'
        digits = 1 if display < 10 and display % 1 else 0
        return f"₹{display:.{digits}f}{suffix}"
    return f"₹{int(round(value))}"


def _pct_change(current_value: Decimal, previous_value: Decimal) -> float:
    current_float = float(current_value)
    previous_float = float(previous_value)

    if previous_float == 0:
        if current_float > 0:
            return 100.0
        if current_float < 0:
            return -100.0
        return 0.0

    return round(((current_float - previous_float) / abs(previous_float)) * 100, 1)


def _build_monthly_weeks(user, month_start: date, month_end: date) -> list[dict]:
    chart_width = 560
    chart_height = 220
    chart_inner_height = 190
    weeks = []
    cursor = month_start
    week_index = 1

    while cursor <= month_end:
        week_end = min(cursor + timedelta(days=6), month_end)
        income = Transaction.objects.filter(
            user=user,
            txn_type='income',
            date__gte=cursor,
            date__lte=week_end,
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        expense = Transaction.objects.filter(
            user=user,
            txn_type='expense',
            date__gte=cursor,
            date__lte=week_end,
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        weeks.append({
            'label': f'Week {week_index}',
            'range_label': f'{cursor.strftime("%b")} {cursor.day} - {week_end.strftime("%b")} {week_end.day}',
            'income': float(income),
            'expense': float(expense),
        })
        cursor = week_end + timedelta(days=1)
        week_index += 1

    if not weeks:
        weeks.append({
            'label': 'Week 1',
            'range_label': f'{month_start.strftime("%b")} {month_start.day} - {month_end.strftime("%b")} {month_end.day}',
            'income': 0.0,
            'expense': 0.0,
        })

    max_val = max(
        max((week['income'] for week in weeks), default=0),
        max((week['expense'] for week in weeks), default=0),
        1,
    )
    slot_width = chart_width / len(weeks)
    bar_width = min(28, max(18, int((slot_width - 22) / 2)))
    bar_gap = min(12, max(8, int(slot_width * 0.12)))
    pair_width = bar_width * 2 + bar_gap
    trend_points = []

    for index, week in enumerate(weeks):
        start_x = index * slot_width + max((slot_width - pair_width) / 2, 4)
        income_height = 0 if week['income'] <= 0 else max(10, round((week['income'] / max_val) * chart_inner_height, 1))
        expense_height = 0 if week['expense'] <= 0 else max(10, round((week['expense'] / max_val) * chart_inner_height, 1))
        income_y = chart_height - income_height
        expense_y = chart_height - expense_height
        income_cx = start_x + bar_width / 2

        week.update({
            'income_height': income_height,
            'expense_height': expense_height,
            'income_y': income_y,
            'expense_y': expense_y,
            'income_x': round(start_x, 1),
            'expense_x': round(start_x + bar_width + bar_gap, 1),
            'bar_width': bar_width,
        })
        trend_points.append({'x': income_cx, 'y': income_y if income_height else chart_height})

    trend_path = ''
    if len(trend_points) > 1:
        trend_path = f"M{trend_points[0]['x']:.1f},{trend_points[0]['y']:.1f}"
        for index in range(1, len(trend_points)):
            prev_point = trend_points[index - 1]
            point = trend_points[index]
            control_x = (prev_point['x'] + point['x']) / 2
            trend_path += (
                f" C{control_x:.1f},{prev_point['y']:.1f}"
                f" {control_x:.1f},{point['y']:.1f}"
                f" {point['x']:.1f},{point['y']:.1f}"
            )

    axis_step = ceil(max_val / 5) if max_val else 1
    y_axis_labels = [
        _format_axis_currency(axis_step * level)
        for level in range(5, -1, -1)
    ]

    return {
        'weeks': weeks,
        'trend_path': trend_path,
        'y_axis_labels': y_axis_labels,
        'max_value': round(max_val, 2),
    }


def _build_monthly_categories(user, month_start: date, month_end: date, total_expense: Decimal) -> list[dict]:
    categories = []
    total_expense_float = float(total_expense)

    for key, label in Transaction.CATEGORY_CHOICES:
        amount = Transaction.objects.filter(
            user=user,
            txn_type='expense',
            category=key,
            date__gte=month_start,
            date__lte=month_end,
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

        if amount <= 0:
            continue

        accent = CATEGORY_ACCENTS.get(key, CATEGORY_ACCENTS['other'])
        categories.append({
            'key': key,
            'label': label,
            'amount': float(amount),
            'share_pct': round((float(amount) / total_expense_float) * 100, 1) if total_expense_float else 0,
            'color': CATEGORY_COLORS.get(key, '#e2e8f0'),
            'icon_bg': accent['bg'],
            'icon_fg': accent['fg'],
        })

    return sorted(categories, key=lambda category: category['amount'], reverse=True)


def _build_monthly_score(total_income: Decimal, total_expense: Decimal, total_saved: Decimal, salary: Decimal) -> dict:
    if salary > 0:
        baseline = float(salary)
    else:
        baseline = float(total_income)

    if baseline > 0:
        spend_ratio = float(total_expense) / baseline
        save_ratio = max(float(total_saved), 0) / baseline
        score = round(max(0, min(100, 100 - (spend_ratio * 62) + min(save_ratio, 1) * 24)))
    else:
        score = 0

    if score >= 80:
        title = 'Excellent rhythm'
        description = "You're keeping spending under control and protecting your savings."
    elif score >= 60:
        title = 'Good standing'
        description = "Your month looks healthy, with room to tighten a few categories."
    elif score >= 40:
        title = 'Needs attention'
        description = 'Spending is starting to crowd out savings this month.'
    else:
        title = 'High pressure'
        description = 'This month is running hot. Review your biggest expense days first.'

    return {
        'value': score,
        'ring_dash': round((score / 100) * MONTHLY_SCORE_CIRCUMFERENCE, 1),
        'ring_gap': round(MONTHLY_SCORE_CIRCUMFERENCE - (score / 100) * MONTHLY_SCORE_CIRCUMFERENCE, 1),
        'title': title,
        'description': description,
    }


def _build_top_spending_days(user, month_start: date, month_end: date) -> list[dict]:
    daily_spend = {}
    badge_classes = ['payment', 'figma', 'withdrawal', 'webflow', 'zalando']

    for txn in Transaction.objects.filter(
        user=user,
        txn_type='expense',
        date__gte=month_start,
        date__lte=month_end,
    ).order_by('date', 'created_at'):
        entry = daily_spend.setdefault(txn.date, {
            'amount': Decimal('0'),
            'categories': {},
        })
        entry['amount'] += txn.amount
        entry['categories'][txn.category] = entry['categories'].get(txn.category, Decimal('0')) + txn.amount

    ranked_days = sorted(daily_spend.items(), key=lambda item: item[1]['amount'], reverse=True)[:5]
    results = []

    for index, (day, payload) in enumerate(ranked_days):
        top_categories = sorted(payload['categories'].items(), key=lambda item: item[1], reverse=True)[:2]
        category_text = ' + '.join(dict(Transaction.CATEGORY_CHOICES).get(key, key.title()) for key, _ in top_categories)
        results.append({
            'day_number': day.day,
            'label': day.strftime('%b %d'),
            'summary': category_text or 'Expenses',
            'amount': float(payload['amount']),
            'badge_class': badge_classes[index % len(badge_classes)],
        })

    return results


def _build_monthly_analysis(user, profile, selected_month: date) -> dict:
    month_start, month_end = _month_bounds(selected_month)
    prev_month_start = _add_months(month_start, -1)
    prev_month_end = month_start - timedelta(days=1)

    month_txns = Transaction.objects.filter(user=user, date__gte=month_start, date__lte=month_end)
    total_income = month_txns.filter(txn_type='income').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    total_expense = month_txns.filter(txn_type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    salary = Decimal(str(profile.salary)) if profile.salary else Decimal('0')
    total_saved = (salary - total_expense) if salary > 0 else (total_income - total_expense)
    total_balance = total_saved

    prev_txns = Transaction.objects.filter(user=user, date__gte=prev_month_start, date__lte=prev_month_end)
    prev_income = prev_txns.filter(txn_type='income').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    prev_expense = prev_txns.filter(txn_type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    prev_saved = (salary - prev_expense) if salary > 0 else (prev_income - prev_expense)

    balance_change_pct = _pct_change(total_balance, prev_saved)
    categories = _build_monthly_categories(user, month_start, month_end, total_expense)
    donut_segments = _build_insight_segments(categories[:4], total_expense)
    weekly_chart = _build_monthly_weeks(user, month_start, month_end)
    monthly_score = _build_monthly_score(total_income, total_expense, total_saved, salary)
    top_spending_days = _build_top_spending_days(user, month_start, month_end)

    if salary > 0:
        spend_ratio = min(round((float(total_expense) / float(salary)) * 100, 1), 999.9)
    elif total_income > 0:
        spend_ratio = min(round((float(total_expense) / float(total_income)) * 100, 1), 999.9)
    else:
        spend_ratio = 0.0

    target = Decimal(str(profile.target_savings)) if profile.target_savings else Decimal('0')
    wealth_progress_pct = min(round((max(float(total_saved), 0) / float(target)) * 100, 1), 100) if target > 0 else 0

    if total_expense <= 0:
        reminder_title = 'Start tracking expenses for this month'
        reminder_sub = 'ADD A FEW TRANSACTIONS TO SEE TRENDS'
    elif monthly_score['value'] >= 75:
        reminder_title = 'Your monthly budget is holding up well'
        reminder_sub = 'KEEP THIS MOMENTUM GOING'
    else:
        reminder_title = 'Review your biggest spending days this month'
        reminder_sub = 'CUT BACK WHERE IT HURTS MOST'

    return {
        'selected_month': month_start,
        'selected_month_param': month_start.strftime('%Y-%m'),
        'selected_month_label': month_start.strftime('%B %Y'),
        'month_period_label': f'{month_start.day} - {month_end.day} {month_end.strftime("%b %Y")}',
        'prev_month_param': _add_months(month_start, -1).strftime('%Y-%m'),
        'next_month_param': _add_months(month_start, 1).strftime('%Y-%m'),
        'is_current_month': month_start == date.today().replace(day=1),
        'account_subtitle': f'{month_txns.count()} transaction{"s" if month_txns.count() != 1 else ""} in this month',
        'month_badge': 'This month' if month_start == date.today().replace(day=1) else month_start.strftime('%b %Y'),
        'total_income': total_income,
        'total_expense': total_expense,
        'total_saved': total_saved,
        'total_balance': total_balance,
        'balance_change_pct': balance_change_pct,
        'balance_change_positive': balance_change_pct >= 0,
        'weekly_chart': weekly_chart,
        'categories': categories[:5],
        'donut_segments': donut_segments,
        'donut_legend': categories[:4],
        'monthly_score': monthly_score,
        'top_spending_days': top_spending_days,
        'reminder_title': reminder_title,
        'reminder_sub': reminder_sub,
        'wealth_amount_label': f'₹{target:,.2f} target' if target > 0 else 'No goal set',
        'wealth_progress_pct': wealth_progress_pct,
        'wealth_sub': (
            f'{wealth_progress_pct:.1f}% of your savings goal reached'
            if target > 0 else
            'Set a savings target to track progress here'
        ),
        'wealth_badge': 'GOALS' if target > 0 else 'START',
        'wealth_cta': (
            'BUILD YOUR GOAL CONSISTENCY'
            if target > 0 else
            'SET A TARGET TO TRACK PROGRESS'
        ),
        'spend_ratio_pct': spend_ratio,
    }


def _build_insight_stock_card(chart_months, total_expense):
    """Create stock-style summary data for the dashboard hero card."""
    latest_expense = float(total_expense)
    previous_expense = chart_months[-2]['expense'] if len(chart_months) > 1 else 0

    if previous_expense > 0:
        change_pct = round(((latest_expense - previous_expense) / previous_expense) * 100, 1)
    elif latest_expense > 0:
        change_pct = 100.0
    else:
        change_pct = 0.0

    return {
        'title': 'Expense Trend',
        'symbol': 'SPND',
        'subtitle': 'Monthly spend',
        'amount': latest_expense,
        'change_pct': change_pct,
        'is_up': change_pct >= 0,
    }


def _dashboard_stats(user, profile):
    """Compute all dynamic stats for the dashboard."""
    today      = date.today()
    month_start = today.replace(day=1)

    txns = Transaction.objects.filter(user=user, date__gte=month_start, date__lte=today)

    total_income  = txns.filter(txn_type='income').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    total_expense = txns.filter(txn_type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')

    # Savings = salary - expenses (if salary set), else income - expenses
    salary = Decimal(str(profile.salary)) if profile.salary else Decimal('0')
    if salary > 0:
        total_saved = salary - total_expense
        total_balance = salary - total_expense
    else:
        total_saved = total_income - total_expense
        total_balance = total_income - total_expense

    # Category breakdown (expenses only)
    cat_data = {}
    for cat, label in Transaction.CATEGORY_CHOICES:
        amt = txns.filter(txn_type='expense', category=cat).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        if amt > 0:
            cat_data[cat] = {
                'label': label,
                'amount': amt,
                'icon': CATEGORY_ICONS.get(cat, '📦'),
                'color': CATEGORY_COLORS.get(cat, '#e2e8f0'),
            }
    cat_tiles = _serialize_category_tiles(cat_data)
    insight_segments = _build_insight_segments(cat_tiles, total_expense)

    # Spend % vs salary
    spend_pct = None
    if profile.salary and float(profile.salary) > 0:
        spend_pct = min(round(float(total_expense) / float(profile.salary) * 100, 1), 100)

    # Savings % vs target
    savings_pct = None
    CIRC = 263.9
    if profile.target_savings and float(profile.target_savings) > 0:
        savings_pct = min(round(float(total_saved) / float(profile.target_savings) * 100, 1), 100)
    ring_dash = round((savings_pct or 0) / 100 * CIRC, 1)

    # Last 7 transactions
    recent_txns = Transaction.objects.filter(user=user).order_by('-date', '-created_at')[:7]

    # Chart: last 6 months saved vs expenses
    chart_months = []
    for i in range(5, -1, -1):
        d = today.replace(day=1) - timedelta(days=i * 28)
        m_start = d.replace(day=1)
        if d.month == 12:
            m_end = d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            m_end = d.replace(month=d.month + 1, day=1) - timedelta(days=1)

        m_exp  = Transaction.objects.filter(
            user=user, txn_type='expense', date__gte=m_start, date__lte=m_end
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        m_inc  = Transaction.objects.filter(
            user=user, txn_type='income', date__gte=m_start, date__lte=m_end
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        m_saved = max(m_inc - m_exp, Decimal('0'))

        chart_months.append({
            'label':   d.strftime('%b'),
            'expense': float(m_exp),
            'saved':   float(m_saved),
        })

    insight_stock = _build_insight_stock_card(chart_months, total_expense)

    return {
        'total_income':  total_income,
        'total_expense': total_expense,
        'total_saved':   total_saved,
        'total_balance': total_balance,
        'cat_data':      cat_data,
        'cat_tiles':     cat_tiles,
        'spend_pct':     spend_pct,
        'savings_pct':   savings_pct,
        'ring_dash':     ring_dash,
        'ring_gap':      round(CIRC - ring_dash, 1),
        'insight_segments': insight_segments,
        'insight_total': total_expense,
        'insight_stock': insight_stock,
        'recent_txns':   recent_txns,
        'chart_months':  chart_months,
    }


# ── Onboarding ────────────────────────────────────────────
def onboarding(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'login/onboarding.html')


# ── Sign Up ───────────────────────────────────────────────
def signup(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        name     = request.POST.get('name', '').strip()
        email    = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        errors = {}
        if not name:
            errors['name'] = 'Name is required.'
        if not email:
            errors['email'] = 'Email is required.'
        elif User.objects.filter(email=email).exists():
            errors['email'] = 'An account with this email already exists.'
        if not password or len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters.'

        if errors:
            return render(request, 'login/signup.html', {'errors': errors, 'form': request.POST})

        username = email
        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=name.split()[0],
            last_name=' '.join(name.split()[1:]) if len(name.split()) > 1 else '',
        )
        UserProfile.objects.create(user=user)
        login(request, user)
        messages.success(request, f'Welcome to SpendWise, {user.first_name}!')
        return redirect('dashboard')

    return render(request, 'login/signup.html')


# ── Login ─────────────────────────────────────────────────
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email    = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        errors = {}
        if not email:
            errors['email'] = 'Email is required.'
        if not password:
            errors['password'] = 'Password is required.'

        if not errors:
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
            else:
                errors['general'] = 'Invalid email or password.'

        return render(request, 'login/login.html', {'errors': errors, 'form': request.POST})

    return render(request, 'login/login.html')


# ── Logout ────────────────────────────────────────────────
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect('onboarding')


# ── Dashboard ─────────────────────────────────────────────
@login_required(login_url='/login/')
def dashboard(request: HttpRequest) -> HttpResponse:
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    stats      = _dashboard_stats(request.user, profile)
    coach      = get_spending_message(stats['spend_pct'])
    dad_joke   = fetch_dad_joke()

    return render(request, 'login/dashboard.html', {
        'user':         request.user,
        'profile':      profile,
        'coach':        coach,
        'dad_joke':     dad_joke,
        'categories':   Transaction.CATEGORY_CHOICES,
        'today':        date.today().isoformat(),
        'active_nav':   'dashboard',
        **stats,
        'chart_months': json.dumps(stats['chart_months']),
        'insight_segments_json': json.dumps(stats['insight_segments']),
    })


# ── Savings Goals Page ────────────────────────────────────
@login_required(login_url='/login/')
def savings(request: HttpRequest) -> HttpResponse:
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    stats      = _dashboard_stats(request.user, profile)
    monthly_saved = stats['total_saved']  # income - expenses this month
    goals      = SavingsGoal.objects.filter(user=request.user)

    # For each goal, progress = monthly_saved / target * 100
    # We pass monthly_saved so template can compute per-goal progress
    CIRC = 263.9
    goals_data = []
    for g in goals:
        if float(g.target_amount) > 0:
            pct = min(round(float(monthly_saved) / float(g.target_amount) * 100, 1), 100)
        else:
            pct = 0
        pct = max(pct, 0)
        goals_data.append({
            'id':            g.id,
            'name':          g.name,
            'target_amount': g.target_amount,
            'progress_pct':  pct,
            'ring_dash':     round(pct / 100 * CIRC, 1),
            'ring_gap':      round(CIRC - pct / 100 * CIRC, 1),
            'is_complete':   float(monthly_saved) >= float(g.target_amount),
            'remaining':     max(float(g.target_amount) - float(monthly_saved), 0),
        })

    return render(request, 'login/savings.html', {
        'user':          request.user,
        'profile':       profile,
        'goals':         goals_data,
        'goal_count':    goals.count(),
        'monthly_saved': monthly_saved,
        'active_nav':    'savings',
    })


# ── API: Create Goal ──────────────────────────────────────
@login_required(login_url='/login/')
@require_POST
def api_create_goal(request: HttpRequest) -> JsonResponse:
    try:
        data   = json.loads(request.body)
        name   = data.get('name', '').strip() or 'My Goal'
        target = float(data.get('target_amount', 0) or 0)
        if target <= 0:
            return JsonResponse({'error': 'Target must be greater than zero.'}, status=400)
        goal = SavingsGoal.objects.create(
            user=request.user, name=name,
            target_amount=Decimal(str(target)), saved_amount=Decimal('0')
        )
        return JsonResponse({'success': True, 'goal': _goal_json(goal)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── API: Update Goal ──────────────────────────────────────
@login_required(login_url='/login/')
@require_http_methods(['PUT'])
def api_update_goal(request: HttpRequest, goal_id: int) -> JsonResponse:
    try:
        goal   = SavingsGoal.objects.get(id=goal_id, user=request.user)
        data   = json.loads(request.body)
        goal.name          = data.get('name', goal.name).strip() or goal.name
        goal.target_amount = Decimal(str(float(data.get('target_amount', goal.target_amount))))
        goal.save()
        return JsonResponse({'success': True, 'goal': _goal_json(goal)})
    except SavingsGoal.DoesNotExist:
        return JsonResponse({'error': 'Not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── API: Delete Goal ──────────────────────────────────────
@login_required(login_url='/login/')
@require_http_methods(['DELETE'])
def api_delete_goal(request: HttpRequest, goal_id: int) -> JsonResponse:
    try:
        goal = SavingsGoal.objects.get(id=goal_id, user=request.user)
        goal.delete()
        return JsonResponse({'success': True})
    except SavingsGoal.DoesNotExist:
        return JsonResponse({'error': 'Not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── API: Contribute to Goal ───────────────────────────────
@login_required(login_url='/login/')
@require_POST
def api_contribute_goal(request: HttpRequest, goal_id: int) -> JsonResponse:
    try:
        goal   = SavingsGoal.objects.get(id=goal_id, user=request.user)
        data   = json.loads(request.body)
        amount = float(data.get('amount', 0) or 0)
        if amount <= 0:
            return JsonResponse({'error': 'Amount must be greater than zero.'}, status=400)
        goal.saved_amount += Decimal(str(amount))
        goal.save()
        return JsonResponse({'success': True, 'goal': _goal_json(goal)})
    except SavingsGoal.DoesNotExist:
        return JsonResponse({'error': 'Not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def _goal_json(goal: 'SavingsGoal') -> dict:
    CIRC = 263.9
    pct  = goal.progress_pct
    return {
        'id':           goal.id,
        'name':         goal.name,
        'target_amount': float(goal.target_amount),
        'saved_amount':  float(goal.saved_amount),
        'progress_pct':  pct,
        'is_complete':   goal.is_complete,
        'ring_dash':     round(pct / 100 * CIRC, 1),
        'ring_gap':      round(CIRC - pct / 100 * CIRC, 1),
    }


# ── Profile ───────────────────────────────────────────────
@login_required(login_url='/login/')
def profile_view(request: HttpRequest) -> HttpResponse:
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    success = False

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip().lower()

        request.user.first_name = first_name
        request.user.last_name  = last_name
        if email and email != request.user.email:
            if not User.objects.filter(email=email).exclude(pk=request.user.pk).exists():
                request.user.email    = email
                request.user.username = email
        request.user.save()

        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
        profile.save()
        success = True

    return render(request, 'login/profile.html', {
        'user':       request.user,
        'profile':    profile,
        'active_nav': 'profile',
        'success':    success,
    })


# ── Monthly Analysis ──────────────────────────────────────
@login_required(login_url='/login/')
def monthly(request: HttpRequest) -> HttpResponse:
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    monthly_analysis = _build_monthly_analysis(
        request.user,
        profile,
        _parse_month_param(request.GET.get('month')),
    )
    return render(request, 'login/monthly.html', {
        'user':       request.user,
        'profile':    profile,
        'active_nav': 'monthly',
        **monthly_analysis,
    })


# ── API: Add Transaction ──────────────────────────────────
@login_required(login_url='/login/')
@require_POST
def api_add_transaction(request: HttpRequest) -> JsonResponse:
    try:
        data     = json.loads(request.body)
        title    = data.get('title', '').strip() or 'Untitled'
        amount   = data.get('amount', 0)
        txn_type = data.get('txn_type', 'expense').strip()
        category = data.get('category', 'other').strip()
        txn_date = data.get('date', str(date.today()))

        if txn_type not in ('income', 'expense'):
            txn_type = 'expense'
        if not amount or float(amount) <= 0:
            amount = 0

        txn = Transaction.objects.create(
            user=request.user,
            title=title,
            amount=Decimal(str(amount)),
            txn_type=txn_type,
            category=category,
            date=txn_date,
            note=data.get('note', ''),
        )

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        stats = _dashboard_stats(request.user, profile)

        return JsonResponse({
            'success': True,
            'txn': {
                'id':       txn.id,
                'title':    txn.title,
                'amount':   float(txn.amount),
                'txn_type': txn.txn_type,
                'category': txn.category,
                'date':     str(txn.date),
                'icon':     CATEGORY_ICONS.get(txn.category, '📦'),
            },
            **_dashboard_stats_payload(stats),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── API: Delete Transaction ───────────────────────────────
@login_required(login_url='/login/')
@require_http_methods(['DELETE'])
def api_delete_transaction(request: HttpRequest, txn_id: int) -> JsonResponse:
    try:
        txn = Transaction.objects.get(id=txn_id, user=request.user)
        txn.delete()
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        stats = _dashboard_stats(request.user, profile)
        return JsonResponse({
            'success':       True,
            **_dashboard_stats_payload(stats),
        })
    except Transaction.DoesNotExist:
        return JsonResponse({'error': 'Transaction not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── API: Set Salary ───────────────────────────────────────
@login_required(login_url='/login/')
@require_POST
def api_set_salary(request: HttpRequest) -> JsonResponse:
    try:
        data   = json.loads(request.body)
        salary = data.get('salary')
        if salary is None or salary == '':
            return JsonResponse({'error': 'Salary is required.'}, status=400)
        salary = float(salary)
        if salary < 0:
            return JsonResponse({'error': 'Salary must be a positive number.'}, status=400)

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.salary = salary
        profile.save()
        stats = _dashboard_stats(request.user, profile)

        return JsonResponse({
            'success': True,
            'salary': float(profile.salary),
            **_dashboard_stats_payload(stats),
        })
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid salary value.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── API: Set Target Savings ───────────────────────────────
@login_required(login_url='/login/')
@require_POST
def api_set_target_savings(request: HttpRequest) -> JsonResponse:
    try:
        data   = json.loads(request.body)
        target = data.get('target_savings')
        if target is None or target == '':
            return JsonResponse({'error': 'Target savings is required.'}, status=400)
        target = float(target)
        if target <= 0:
            return JsonResponse({'error': 'Target must be greater than zero.'}, status=400)

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.target_savings = target
        profile.save()

        stats = _dashboard_stats(request.user, profile)

        return JsonResponse({
            'success':     True,
            'target':      float(profile.target_savings),
            'savings_pct': stats['savings_pct'],
            'ring_dash':   stats['ring_dash'],
            'ring_gap':    stats['ring_gap'],
        })
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid value.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
