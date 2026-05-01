from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html

from .models import Transaction, UserProfile, SavingsGoal


# ── Custom admin site ──────────────────────────────────────
class SpendWiseAdminSite(admin.AdminSite):
    site_header = 'SpendWise Admin'
    site_title  = 'SpendWise'
    index_title = 'Dashboard'

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['analytics_url'] = '/admin/analytics/'
        return super().index(request, extra_context)


admin.site.site_header = 'SpendWise Admin'
admin.site.site_title  = 'SpendWise'
admin.site.index_title = 'Welcome to SpendWise Admin'


# ── UserProfile inline (shows inside User admin) ──────────
class UserProfileInline(admin.StackedInline):
    model   = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields  = ('salary', 'target_savings', 'created_at')
    readonly_fields = ('created_at',)


# ── Extend the default User admin ─────────────────────────
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = (
        'username', 'email', 'first_name', 'last_name',
        'is_staff', 'is_active', 'date_joined', 'get_salary',
    )
    list_filter  = ('is_staff', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering     = ('-date_joined',)

    @admin.display(description='Salary')
    def get_salary(self, obj):
        try:
            s = obj.profile.salary
            return f'${s:,.2f}' if s else '—'
        except UserProfile.DoesNotExist:
            return '—'


# Re-register User with the extended admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# ── Standalone UserProfile admin ──────────────────────────
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'get_email', 'salary', 'target_savings', 'created_at')
    list_filter   = ('created_at',)
    search_fields = ('user__username', 'user__email', 'user__first_name')
    readonly_fields = ('created_at',)
    ordering      = ('-created_at',)

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Financial', {
            'fields': ('salary', 'target_savings')
        }),
        ('Meta', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Email')
    def get_email(self, obj):
        return obj.user.email


# ── Transaction admin ──────────────────────────────────────
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ('user', 'title', 'txn_type', 'category', 'amount', 'date', 'created_at')
    list_filter   = ('txn_type', 'category', 'date')
    search_fields = ('user__username', 'user__email', 'title', 'note')
    ordering      = ('-date', '-created_at')
    date_hierarchy = 'date'
    readonly_fields = ('created_at',)

    fieldsets = (
        ('Transaction', {
            'fields': ('user', 'title', 'amount', 'txn_type', 'category', 'date', 'note')
        }),
        ('Meta', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )


# ── Savings Goal admin ─────────────────────────────────────
@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display  = ('user', 'name', 'target_amount', 'saved_amount', 'progress_pct', 'is_complete', 'created_at')
    list_filter   = ('created_at',)
    search_fields = ('user__username', 'user__email', 'name')
    ordering      = ('-created_at',)
    readonly_fields = ('created_at',)

    @admin.display(description='Progress %')
    def progress_pct(self, obj):
        return f"{obj.progress_pct}%"

    @admin.display(description='Complete', boolean=True)
    def is_complete(self, obj):
        return obj.is_complete
