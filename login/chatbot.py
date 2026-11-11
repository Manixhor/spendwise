import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import RecurringPayment, Transaction, UserProfile
from .views import _daily_spending_allowance


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def chatbot_tools(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            txn_id = int(data.get("transaction_id"))
            category = data.get("category")
        except (ValueError, TypeError, json.JSONDecodeError):
            return JsonResponse({"error": "Choose a transaction and category."}, status=400)
        valid_categories = {key for key, _ in Transaction.CATEGORY_CHOICES}
        if category not in valid_categories or category == "lend":
            return JsonResponse({"error": "Choose a valid category."}, status=400)
        txn = Transaction.objects.filter(
            pk=txn_id, user=request.user, txn_type="expense", split_parent__isnull=True,
        ).first()
        if txn is None:
            return JsonResponse({"error": "Transaction not found."}, status=404)
        if txn.category == "lend":
            return JsonResponse({"error": "Lend items must be edited in the Lend Tracker."}, status=400)
        txn.category = category
        txn.save(update_fields=["category"])
        return JsonResponse({"success": True, "title": txn.title,
                             "category": dict(Transaction.CATEGORY_CHOICES)[category]})

    today = timezone.localdate()
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    allowance = _daily_spending_allowance(today, profile)
    payments = RecurringPayment.objects.filter(
        user=request.user, active=True, next_due__gte=today,
        next_due__lte=today + timedelta(days=30),
    ).order_by("next_due", "name")[:8]
    recent = Transaction.objects.filter(
        user=request.user, txn_type="expense", split_parent__isnull=True,
    ).exclude(category="lend").order_by("-date", "-created_at", "-pk")[:8]
    return JsonResponse({
        "success": True,
        "allowance": {key: str(value) for key, value in allowance.items()} if allowance else None,
        "salary_set": bool(profile.salary and profile.salary > 0),
        "payments": [{"name": item.name, "amount": str(item.amount),
                      "date": item.next_due.isoformat()} for item in payments],
        "recent": [{"id": item.pk, "title": item.title, "amount": str(item.amount),
                    "date": item.date.isoformat(), "category": item.category} for item in recent],
        "categories": [{"key": key, "label": label} for key, label in Transaction.CATEGORY_CHOICES if key != "lend"],
    })
