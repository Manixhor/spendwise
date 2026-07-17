from django.db import models
from django.contrib.auth.models import User


class ExcessIncome(models.Model):
    """Track additional income beyond regular salary for specific months"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="excess_incomes")
    month = models.CharField(max_length=7, help_text="YYYY-MM format, e.g. '2025-05'")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "month"]
        ordering = ["-month"]

    def __str__(self):
        return f"{self.user.username} – {self.month} – ₹{self.amount}"


class UserProfile(models.Model):
    PRIORITY_CHOICES = [
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_savings = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="medium"
    )
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    email_is_verified = models.BooleanField(default=False)
    email_verification_code = models.CharField(max_length=6, blank=True, default="")
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} – profile"


class Transaction(models.Model):
    CATEGORY_CHOICES = [
        ("rent", "Rent"),
        ("transport", "Transport"),
        ("health", "Health"),
        ("groceries", "Groceries"),
        ("entertainment", "Entertainment"),
        ("shopping", "Shopping"),
        ("food", "Food"),
        ("utilities", "Utilities"),
        ("other", "Other"),
    ]
    TYPE_CHOICES = [
        ("income", "Income"),
        ("expense", "Expense"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="transactions"
    )
    title = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    txn_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="other"
    )
    date = models.DateField()
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        sign = "+" if self.txn_type == "income" else "-"
        return f"{self.user.username} | {self.title} {sign}₹{self.amount}"


class SavingsGoal(models.Model):
    PRIORITY_CHOICES = [
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="savings_goals"
    )
    name = models.CharField(max_length=120)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    saved_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="medium"
    )
    allocation_percentage = models.PositiveIntegerField(
        default=50, help_text="Percentage of available savings to allocate (0-100)"
    )
    is_active = models.BooleanField(
        default=True, help_text="Goal is still being funded"
    )
    last_allocated_month = models.CharField(
        max_length=7, blank=True, default="",
        help_text="YYYY-MM of the last month allocation was applied, e.g. '2025-05'"
    )
    current_month_auto_allocation = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Auto-allocation for current month (reversible)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} – {self.name}"

    @property
    def progress_pct(self):
        if self.target_amount > 0:
            effective_saved = min(
                self.saved_amount + self.current_month_auto_allocation,
                self.target_amount,
            )
            return min(
                round(float(effective_saved) / float(self.target_amount) * 100, 1),
                100,
            )
        return 0

    @property
    def is_complete(self):
        effective_saved = min(self.saved_amount + self.current_month_auto_allocation, self.target_amount)
        return effective_saved >= self.target_amount

    @property
    def remaining(self):
        effective_saved = min(self.saved_amount + self.current_month_auto_allocation, self.target_amount)
        return max(self.target_amount - effective_saved, 0)

    @property
    def is_active_goal(self):
        effective_saved = min(self.saved_amount + self.current_month_auto_allocation, self.target_amount)
        return self.is_active and effective_saved < self.target_amount


class PageView(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="page_views")
    path = models.CharField(max_length=255)
    view_count = models.PositiveIntegerField(default=0)
    last_viewed = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_viewed"]

    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        return f"{user_str} | {self.path} — {self.view_count} views"
