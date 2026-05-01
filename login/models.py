from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    salary         = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_savings = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    avatar         = models.ImageField(upload_to='avatars/', null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} – profile"


class Transaction(models.Model):
    CATEGORY_CHOICES = [
        ('rent',          'Rent'),
        ('transport',     'Transport'),
        ('health',        'Health'),
        ('groceries',     'Groceries'),
        ('entertainment', 'Entertainment'),
        ('shopping',      'Shopping'),
        ('food',          'Food'),
        ('utilities',     'Utilities'),
        ('other',         'Other'),
    ]
    TYPE_CHOICES = [
        ('income',  'Income'),
        ('expense', 'Expense'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    title       = models.CharField(max_length=120)
    amount      = models.DecimalField(max_digits=12, decimal_places=2)
    txn_type    = models.CharField(max_length=10, choices=TYPE_CHOICES)
    category    = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    date        = models.DateField()
    note        = models.TextField(blank=True, default='')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        sign = '+' if self.txn_type == 'income' else '-'
        return f"{self.user.username} | {self.title} {sign}₹{self.amount}"


class SavingsGoal(models.Model):
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='savings_goals')
    name          = models.CharField(max_length=120)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    saved_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} – {self.name}"

    @property
    def progress_pct(self):
        if self.target_amount > 0:
            return min(round(float(self.saved_amount) / float(self.target_amount) * 100, 1), 100)
        return 0

    @property
    def is_complete(self):
        return self.saved_amount >= self.target_amount