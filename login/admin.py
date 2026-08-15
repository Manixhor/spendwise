from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .monthly_mailer import send_monthly_analysis_batch
from .models import MonthlyAnalysisMailSetting, Transaction, UserProfile, SavingsGoal


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


@admin.register(MonthlyAnalysisMailSetting)
class MonthlyAnalysisMailSettingAdmin(admin.ModelAdmin):
    change_list_template = 'admin/login/monthlyanalysismailsetting/change_list.html'
    list_display = (
        'enabled',
        'send_day',
        'send_time',
        'last_sent_month',
        'last_sent_at',
        'updated_at',
    )
    readonly_fields = ('last_sent_month', 'last_sent_at', 'updated_at')

    fieldsets = (
        ('Schedule', {
            'fields': ('enabled', 'send_day', 'send_time')
        }),
        ('Last Run', {
            'fields': ('last_sent_month', 'last_sent_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        if MonthlyAnalysisMailSetting.objects.exists():
            return False
        return super().has_add_permission(request)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'send-now/',
                self.admin_site.admin_view(self.send_now),
                name='login_monthlyanalysismailsetting_send_now',
            ),
        ]
        return custom_urls + urls

    def send_now(self, request):
        if request.method != 'POST':
            return redirect('admin:login_monthlyanalysismailsetting_changelist')

        month = timezone.localtime().strftime('%Y-%m')
        result = send_monthly_analysis_batch(month)
        if result['failed']:
            self.message_user(
                request,
                f"Sent {result['sent']} monthly analysis email(s) for {month}; {result['failed']} failed.",
                level=messages.WARNING,
            )
        else:
            self.message_user(
                request,
                f"Sent {result['sent']} monthly analysis email(s) for {month}.",
                level=messages.SUCCESS,
            )
        return redirect('admin:login_monthlyanalysismailsetting_changelist')


# ── Transaction admin ──────────────────────────────────────
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ('user', 'title', 'txn_type', 'category', 'amount', 'is_settled', 'date', 'created_at')
    list_filter   = ('txn_type', 'category', 'is_settled', 'date')
    search_fields = ('user__username', 'user__email', 'title', 'note')
    ordering      = ('-date', '-created_at')
    date_hierarchy = 'date'
    readonly_fields = ('created_at',)

    fieldsets = (
        ('Transaction', {
            'fields': ('user', 'title', 'amount', 'txn_type', 'category', 'is_settled', 'date', 'note')
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
