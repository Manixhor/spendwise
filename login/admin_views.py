"""
Custom admin dashboard view with charts.
Accessible at /admin/dashboard/
"""
import json
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.db.models import Count, OuterRef, Subquery, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import PageView, Transaction, UserProfile


def superuser_required(view):
    return user_passes_test(
        lambda user: user.is_active and user.is_superuser,
        login_url='/admin/login/',
    )(view)


def _month_start(month: date, offset: int) -> date:
    """Return the first day of the month that is ``offset`` months earlier."""
    month_number = month.month - offset
    year = month.year
    while month_number <= 0:
        month_number += 12
        year -= 1
    return date(year, month_number, 1)


@superuser_required
def admin_dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    week_start = today - timedelta(days=6)

    # ── User stats ─────────────────────────────────────────
    total_users = User.objects.filter(is_staff=False).count()
    new_this_week = User.objects.filter(
        is_staff=False,
        date_joined__date__gte=week_start
    ).count()
    users_with_salary = UserProfile.objects.filter(
        user__is_staff=False,
        salary__isnull=False,
    ).count()

    # ── Transaction stats ──────────────────────────────────
    customer_transactions = Transaction.objects.filter(user__is_staff=False)
    total_txns = customer_transactions.count()
    total_income = customer_transactions.filter(txn_type='income').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    total_expense = customer_transactions.filter(txn_type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')

    # ── Users enrolled per day (last 30 days) ─────────────
    enroll_qs = (
        User.objects
        .filter(is_staff=False, date_joined__date__gte=today - timedelta(days=29))
        .annotate(day=TruncDate('date_joined'))
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
        customer_transactions
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
        m_start = _month_start(month_start, i)
        if m_start.month == 12:
            m_end = m_start.replace(year=m_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            m_end = m_start.replace(month=m_start.month + 1, day=1) - timedelta(days=1)

        inc = customer_transactions.filter(
            txn_type='income', date__gte=m_start, date__lte=m_end
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        exp = customer_transactions.filter(
            txn_type='expense', date__gte=m_start, date__lte=m_end
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

        monthly_labels.append(m_start.strftime('%b %Y'))
        monthly_income.append(float(inc))
        monthly_expense.append(float(exp))

    # ── Category breakdown (all time) ─────────────────────
    cat_qs = (
        customer_transactions
        .filter(txn_type='expense')
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    cat_labels = [r['category'].title() for r in cat_qs]
    cat_data   = [float(r['total']) for r in cat_qs]

    # ── Top 5 users by spending ────────────────────────────
    top_users = (
        customer_transactions
        .filter(txn_type='expense')
        .values('user__username', 'user__email')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:5]
    )

    # ── Recent signups ─────────────────────────────────────
    recent_users_qs = list(
        User.objects.filter(is_staff=False).order_by('-date_joined')[:20]
    )
    recent_users = [
        {
            'username': u.username,
            'full_name': u.get_full_name() or u.username,
            'email': u.email,
            'date_joined': u.date_joined,
        }
        for u in recent_users_qs
    ]

    latest_page_view = PageView.objects.filter(user=OuterRef('pk')).order_by('-last_viewed')
    recent_active_users = []
    for user in (
        User.objects.filter(is_staff=False, page_views__isnull=False)
        .annotate(
            last_active=Subquery(latest_page_view.values('last_viewed')[:1]),
            last_page=Subquery(latest_page_view.values('path')[:1]),
        )
        .order_by('-last_active')[:10]
    ):
        hours_since_active = round(
            (timezone.now() - user.last_active).total_seconds() / 3600,
            1,
        )
        recent_active_users.append({
            'full_name': user.get_full_name() or user.username,
            'email': user.email,
            'last_page': user.last_page,
            'last_active_hrs': hours_since_active,
        })

    page_views = PageView.objects.all()[:20]
    total_page_views = PageView.objects.aggregate(total=Sum('view_count'))['total'] or 0

    # ── Page views per day (last 30 days) ─────────────────
    pv_qs = (
        PageView.objects
        .filter(last_viewed__date__gte=today - timedelta(days=29))
        .annotate(day=TruncDate('last_viewed'))
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
        'recent_active_users': recent_active_users,
        # Admin context
        'title':              'SpendWise Analytics',
        'has_permission':     True,
    }
    return render(request, 'admin/dashboard.html', context)


@superuser_required
def admin_broadcast(request):
    recipient_count = (
        User.objects
        .filter(is_active=True, email__gt='')
        .exclude(email__isnull=True)
        .values('email')
        .distinct()
        .count()
    )

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('message', '').strip()
        errors = {}

        if not subject:
            errors['subject'] = 'Subject is required.'
        elif len(subject) > 160:
            errors['subject'] = 'Keep the subject to 160 characters or fewer.'
        if not body:
            errors['message'] = 'Message is required.'
        elif len(body) > 10000:
            errors['message'] = 'Keep the message to 10,000 characters or fewer.'

        recipients = list(
            User.objects
            .filter(is_active=True, email__gt='')
            .exclude(email__isnull=True)
            .values_list('email', flat=True)
            .distinct()
        )

        if not recipients:
            errors['general'] = 'No active users with email addresses were found.'

        if errors:
            return render(request, 'admin/broadcast.html', {
                'title': 'Send Broadcast Message',
                'errors': errors,
                'form': {'subject': subject, 'message': body},
                'recipient_count': recipient_count,
                'email_backend': settings.EMAIL_BACKEND,
            })

        try:
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.DEFAULT_FROM_EMAIL],
                bcc=recipients,
                reply_to=[settings.DEFAULT_FROM_EMAIL],
            )
            sent_count = email.send(fail_silently=False)
        except Exception:
            return render(request, 'admin/broadcast.html', {
                'title': 'Send Broadcast Message',
                'errors': {
                    'general': 'The broadcast could not be sent. Check the email service settings and try again.',
                },
                'form': {'subject': subject, 'message': body},
                'recipient_count': recipient_count,
                'email_backend': settings.EMAIL_BACKEND,
            })

        if sent_count:
            messages.success(
                request,
                f'Broadcast queued for {len(recipients)} user email address(es).'
            )
        else:
            messages.error(request, 'Email backend did not send the broadcast.')
        return redirect('admin_broadcast')

    return render(request, 'admin/broadcast.html', {
        'title': 'Send Broadcast Message',
        'recipient_count': recipient_count,
        'email_backend': settings.EMAIL_BACKEND,
    })
