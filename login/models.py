import datetime
from datetime import date

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from .security import validate_avatar


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
    CURRENCY_CHOICES = [
        ("inr", "₹ INR"),
        ("usd", "$ USD"),
    ]
    CURRENCY_SYMBOLS = {
        "inr": "₹",
        "usd": "$",
    }

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    currency = models.CharField(max_length=5, choices=CURRENCY_CHOICES, default="inr")
    salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_savings = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="medium"
    )
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True, validators=[validate_avatar])
    email_is_verified = models.BooleanField(default=False)
    email_verification_code = models.CharField(max_length=128, blank=True, default="")
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    password_reset_code = models.CharField(max_length=128, blank=True, default="")
    password_reset_sent_at = models.DateTimeField(null=True, blank=True)
    reminders_enabled = models.BooleanField(default=False)
    last_budget_reminder_month = models.CharField(max_length=7, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} – profile"

    @property
    def currency_symbol(self):
        return self.CURRENCY_SYMBOLS.get(self.currency, "₹")

    @property
    def is_usd(self):
        return self.currency == "usd"


class MonthlyAnalysisMailSetting(models.Model):
    enabled = models.BooleanField(
        default=True,
        help_text="Turn automatic monthly report emails on or off.",
    )
    send_day = models.PositiveSmallIntegerField(
        default=8,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text="Choose a day from 1 to 28. Automatic emails contain the previous completed month's report.",
    )
    send_time = models.TimeField(
        default=datetime.time(0, 0),
        help_text="Send time in Asia/Kolkata.",
    )
    last_sent_month = models.CharField(
        max_length=7,
        blank=True,
        default="",
        help_text="YYYY-MM report month last sent by the scheduled command.",
    )
    last_sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    send_day_8_enabled = models.BooleanField(
        default=False,
        help_text="Also send on 8th of the month at 00:00 IST.",
    )
    last_sent_month_day8 = models.CharField(
        max_length=7,
        blank=True,
        default="",
        help_text="YYYY-MM last sent by the 8th schedule.",
    )

    class Meta:
        verbose_name = "Monthly Email Schedule"
        verbose_name_plural = "Monthly Email Schedule"

    def __str__(self):
        status = "Enabled" if self.enabled else "Disabled"
        return f"{status} - day {self.send_day} at {self.send_time:%H:%M}"


class MonthlyAnalysisDelivery(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    month = models.CharField(max_length=7)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'month'], name='unique_monthly_analysis_delivery')]


class AutomationState(models.Model):
    next_check_at = models.DateTimeField()


class ScheduledTestMail(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    report_month = models.CharField(max_length=7)
    scheduled_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=250, blank=True, default='')


class PushKey(models.Model):
    private_key = models.TextField()
    public_key = models.TextField()


class PhoneSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField()
    auth = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class PhoneNotificationDelivery(models.Model):
    subscription = models.ForeignKey(PhoneSubscription, on_delete=models.CASCADE)
    payment = models.ForeignKey('RecurringPayment', on_delete=models.CASCADE)
    due_date = models.DateField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['subscription', 'payment', 'due_date'], name='unique_phone_payment_notice')]


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
        ("lend", "Lend"),
        ("other", "Other"),
    ]
    TYPE_CHOICES = [
        ("income", "Income"),
        ("expense", "Expense"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="transactions"
    )
    account = models.ForeignKey(
        "MoneyAccount", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="transactions",
    )
    title = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    txn_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="other"
    )
    date = models.DateField()
    note = models.TextField(blank=True, default="")
    is_settled = models.BooleanField(
        default=False,
        help_text="Marks lending transactions as paid back.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        sign = "+" if self.txn_type == "income" else "-"
        return f"{self.user.username} | {self.title} {sign}₹{self.amount}"


class MoneyAccount(models.Model):
    KIND_CHOICES = [("cash", "Cash"), ("bank", "Bank"), ("card", "Credit card"), ("wallet", "Wallet")]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="money_accounts")
    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["user", "name"], name="unique_user_money_account_name")]

    def __str__(self):
        return self.name


class RecurringPayment(models.Model):
    KIND_CHOICES = [("bill", "Bill"), ("subscription", "Subscription")]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recurring_payments")
    name = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES)
    category = models.CharField(max_length=20, choices=Transaction.CATEGORY_CHOICES, default="other")
    account = models.ForeignKey(MoneyAccount, null=True, blank=True, on_delete=models.SET_NULL)
    next_due = models.DateField()
    day_of_month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)])
    active = models.BooleanField(default=True)
    auto_record = models.BooleanField(default=False)
    last_recorded_due = models.DateField(null=True, blank=True)
    last_reminded_due = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["next_due", "name"]

    def __str__(self):
        return self.name


class OfficeBalance(models.Model):
    """Opening cash balance for the office tracker, kept separate from SpendWise."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="office_balance"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} – office opening balance {self.amount}"


class OfficeEntry(models.Model):
    """A single 'money out' or 'money in' movement in the office tracker."""

    DIRECTION_CHOICES = [
        ("taken", "Money Out"),
        ("came", "Money In"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="office_entries"
    )
    direction = models.CharField(max_length=5, choices=DIRECTION_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    name = models.CharField(
        max_length=80, blank=True, default="", db_index=True,
        help_text="Person who sent (money in) or received (money out) it.",
    )
    note = models.CharField(max_length=200, blank=True, default="")
    entry_date = models.DateField(
        default=date.today, help_text="Date this movement belongs to."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-entry_date", "-created_at"]

    def __str__(self):
        sign = "+" if self.direction == "came" else "-"
        return f"{self.user.username} | office {self.direction} {sign}{self.amount}"

    @property
    def signed_amount(self):
        return self.amount if self.direction == "came" else -self.amount


class OfficeHiddenSuggestion(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="office_hidden_suggestions"
    )
    name_key = models.CharField(max_length=240)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name_key"], name="office_hidden_name_per_user"
            )
        ]


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


class GoldPriceQuote(models.Model):
    """Shared INR spot quotes for rolling 24-hour comparisons."""
    quoted_at = models.DateTimeField(unique=True)
    price = models.FloatField()


class AuthAttemptWindow(models.Model):
    key = models.CharField(max_length=64, unique=True)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
