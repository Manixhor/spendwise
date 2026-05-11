"""
Custom admin dashboard view with charts.
Accessible at /admin/dashboard/
"""
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.timezone import now

from .models import PageView, Transaction, UserProfile


@staff_member_required
def admin_dashboard(request):
    today      = date.today()
    month_start = today.replace(day=1)
    week_start  = today - timedelta(days=6)

    # ── User stats ─────────────────────────────────────────
    total_users   = User.objects.filter(is_staff=False).count()
    active_users  = User.objects.filter(
        is_staff=False,
        transactions__date__gte=month_start
    ).distinct().count()
    new_this_week = User.objects.filter(
        is_staff=False,
        date_joined__date__gte=week_start
    ).count()
    users_with_salary = UserProfile.objects.filter(salary__isnull=False).count()

    # ── Transaction stats ──────────────────────────────────
    total_txns    = Transaction.objects.count()
    total_income  = Transaction.objects.filter(txn_type='income').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    total_expense = Transaction.objects.filter(txn_type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')

    # ── Users enrolled per day (last 30 days) ─────────────
    enroll_qs = (
        User.objects
        .filter(is_staff=False, date_joined__date__gte=today - timedelta(days=29))
        .extra(select={'day': "date(date_joined)"})
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    enroll_map = {str(r['day']): r['count'] for r in enroll_qs}
    enroll_labels, enroll_data = [], []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        enroll_labels.append(d.strftime('%b %d'))
        enroll_data.append(enroll_map.get(str(d), 0))

    # ── Transactions per day (last 30 days) ────────────────
    txn_qs = (
        Transaction.objects
        .filter(date__gte=today - timedelta(days=29))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    txn_map = {str(r['date']): r['count'] for r in txn_qs}
    txn_labels, txn_data = [], []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        txn_labels.append(d.strftime('%b %d'))
        txn_data.append(txn_map.get(str(d), 0))

    # ── Income vs Expense per month (last 6 months) ────────
    monthly_labels, monthly_income, monthly_expense = [], [], []
    for i in range(5, -1, -1):
        d = today.replace(day=1) - timedelta(days=i * 28)
        m_start = d.replace(day=1)
        if d.month == 12:
            m_end = d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            m_end = d.replace(month=d.month + 1, day=1) - timedelta(days=1)

        inc = Transaction.objects.filter(
            txn_type='income', date__gte=m_start, date__lte=m_end
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        exp = Transaction.objects.filter(
            txn_type='expense', date__gte=m_start, date__lte=m_end
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

        monthly_labels.append(d.strftime('%b %Y'))
        monthly_income.append(float(inc))
        monthly_expense.append(float(exp))

    # ── Category breakdown (all time) ─────────────────────
    cat_qs = (
        Transaction.objects
        .filter(txn_type='expense')
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    cat_labels = [r['category'].title() for r in cat_qs]
    cat_data   = [float(r['total']) for r in cat_qs]

    # ── Top 5 users by spending ────────────────────────────
    top_users = (
        Transaction.objects
        .filter(txn_type='expense')
        .values('user__username', 'user__email')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:5]
    )

    # ── Recent signups ─────────────────────────────────────
    recent_users_qs = User.objects.filter(is_staff=False).order_by('-date_joined')[:8]
    recent_users = []
    for u in recent_users_qs:
        if u.last_login:
            delta = now() - u.last_login
            last_active_hrs = round(delta.total_seconds() / 3600, 1)
        else:
            last_active_hrs = None
        recent_users.append({
            'username': u.username,
            'full_name': u.get_full_name() or u.username,
            'email': u.email,
            'date_joined': u.date_joined,
            'last_active_hrs': last_active_hrs,
        })

    page_views = PageView.objects.all()[:20]
    total_page_views = sum(pv.view_count for pv in PageView.objects.all())

    # ── Page views per day (last 30 days) ─────────────────
    pv_qs = (
        PageView.objects
        .filter(last_viewed__date__gte=today - timedelta(days=29))
        .extra(select={'day': "date(last_viewed)"})
        .values('day')
        .annotate(count=Sum('view_count'))
        .order_by('day')
    )
    pv_map = {str(r['day']): r['count'] for r in pv_qs}
    pv_labels, pv_data = [], []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        pv_labels.append(d.strftime('%b %d'))
        pv_data.append(pv_map.get(str(d), 0))

    context = {
        # Stats
        'total_users':        total_users,
        'active_users':       active_users,
        'new_this_week':      new_this_week,
        'users_with_salary':  users_with_salary,
        'total_txns':         total_txns,
        'total_income':       float(total_income),
        'total_expense':      float(total_expense),
        # Page views
        'page_views':         page_views,
        'total_page_views':   total_page_views,
        # Chart data (JSON)
        'pv_labels':          json.dumps(pv_labels),
        'pv_data':            json.dumps(pv_data),
        'enroll_labels':      json.dumps(enroll_labels),
        'enroll_data':        json.dumps(enroll_data),
        'txn_labels':         json.dumps(txn_labels),
        'txn_data':           json.dumps(txn_data),
        'monthly_labels':     json.dumps(monthly_labels),
        'monthly_income':     json.dumps(monthly_income),
        'monthly_expense':    json.dumps(monthly_expense),
        'cat_labels':         json.dumps(cat_labels),
        'cat_data':           json.dumps(cat_data),
        # Tables
        'top_users':          top_users,
        'recent_users':       recent_users,
        # Admin context
        'title':              'SpendWise Analytics',
        'has_permission':     True,
    }
    return render(request, 'admin/dashboard.html', context)
