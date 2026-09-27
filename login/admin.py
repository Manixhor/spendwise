from django.conf import settings
from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.utils.html import format_html
from django.template.loader import render_to_string

from .monthly_mailer import send_monthly_analysis_batch
from .models import MonthlyAnalysisMailSetting, Transaction, UserProfile, SavingsGoal
from .views import send_monthly_analysis_email


admin.site.site_header = 'SpendWise Admin'
admin.site.site_title  = 'SpendWise'
admin.site.index_title = 'Welcome to SpendWise Admin'
admin.site.index_template = 'admin/index.html'


class ManualUserCreationForm(forms.ModelForm):
    """Create an invited customer with an email as their login identifier."""

    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('email',)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('A user with this email address already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        self.temporary_password = get_random_string(
            14,
            allowed_chars='abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789',
        )
        user.set_password(self.temporary_password)
        if commit:
            user.save()
        return user


class SendMonthlyAnalysisToUserForm(forms.Form):
    recipient = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label='Recipient',
        empty_label='Choose a user',
    )
    report_month = forms.DateField(
        label='Report month',
        input_formats=['%Y-%m'],
        widget=forms.DateInput(attrs={'type': 'month'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recipient'].queryset = User.objects.filter(
            is_active=True,
            is_staff=False,
            email__gt='',
        ).order_by('email')
        self.fields['report_month'].initial = timezone.localdate().replace(day=1)


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
    add_form = ManualUserCreationForm
    change_list_template = 'admin/auth/user/change_list.html'
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email',),
            'description': 'A temporary password and sign-in link will be sent to this email address.',
        }),
    )
    list_display = (
        'username', 'delete_account', 'email', 'first_name', 'last_name',
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

    @admin.display(description='Actions')
    def delete_account(self, obj):
        delete_url = reverse('admin:auth_user_delete', args=[obj.pk])
        return format_html(
            '<a href="{}" class="sw-delete-user" title="Delete {}">'
            '<span class="material-symbols-outlined" aria-hidden="true">delete</span>'
            '<span>Delete</span></a>',
            delete_url,
            obj.get_username(),
        )

    def get_inline_instances(self, request, obj=None):
        # A profile is created by the user post-save signal, so it is not needed
        # while the initial account form is being submitted.
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change or obj.is_staff:
            return

        password = getattr(form, 'temporary_password', '')
        if not obj.email or not password:
            return

        profile, _ = UserProfile.objects.get_or_create(user=obj)
        profile.email_is_verified = False
        profile.email_verification_code = ''
        profile.email_verification_sent_at = None
        profile.save(update_fields=[
            'email_is_verified',
            'email_verification_code',
            'email_verification_sent_at',
        ])

        login_url = request.build_absolute_uri(reverse('login'))

        def send_welcome_email():
            try:
                subject = 'Your SpendWise account is ready'
                text_body = (
                    'Welcome to SpendWise.\n\n'
                    'An administrator created a SpendWise account for you.\n\n'
                    f'Login email: {obj.email}\n'
                    f'Temporary password: {password}\n\n'
                    f'Sign in here: {login_url}\n\n'
                    'After signing in, verify your email with a 4-digit OTP and complete your profile.\n\n'
                    'SpendWise'
                )
                html_body = render_to_string('login/emails/manual_user_invite.html', {
                    'email': obj.email,
                    'temporary_password': password,
                    'login_url': login_url,
                })
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[obj.email],
                )
                email.attach_alternative(html_body, 'text/html')
                email.send(fail_silently=False)
            except Exception:
                self.message_user(
                    request,
                    f'User created, but the welcome email could not be sent to {obj.email}.',
                    level=messages.WARNING,
                )

        transaction.on_commit(send_welcome_email)


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
        'schedule_status',
        'last_sent_month',
        'last_sent_at',
        'updated_at',
    )
    readonly_fields = ('last_sent_month', 'last_sent_at', 'updated_at')

    fieldsets = (
        ('Automatic delivery', {
            'fields': ('enabled', 'send_day', 'send_time')
        }),
        ('Delivery history', {
            'fields': ('last_sent_month', 'last_sent_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        if MonthlyAnalysisMailSetting.objects.exists():
            return False
        return super().has_add_permission(request)

    @admin.display(description='Schedule')
    def schedule_status(self, obj):
        if obj.enabled:
            return f'On: day {obj.send_day} at {obj.send_time:%H:%M} IST'
        return 'Off'

    def changelist_view(self, request, extra_context=None):
        MonthlyAnalysisMailSetting.objects.get_or_create(pk=1)
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'send-now/',
                self.admin_site.admin_view(self.send_now),
                name='login_monthlyanalysismailsetting_send_now',
            ),
            path(
                'send-to-user/',
                self.admin_site.admin_view(self.send_to_user),
                name='login_monthlyanalysismailsetting_send_to_user',
            ),
        ]
        return custom_urls + urls

    def send_now(self, request):
        if request.method != 'POST':
            return redirect('admin:login_monthlyanalysismailsetting_changelist')

        setting, _ = MonthlyAnalysisMailSetting.objects.get_or_create(pk=1)
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            self.message_user(
                request,
                "SMTP is not configured for this service. Emails are only printing to logs.",
                level=messages.ERROR,
            )
            return redirect('admin:login_monthlyanalysismailsetting_changelist')

        month = timezone.localtime().strftime('%Y-%m')
        # Send now is intentionally manual: it may be used to resend a report
        # even while automation is paused or after this month's scheduled run.
        result = send_monthly_analysis_batch(month)
        if result['failed']:
            first_error = result['failures'][0] if result['failures'] else 'Unknown error'
            self.message_user(
                request,
                (
                    f"Sent {result['sent']} monthly analysis email(s) for {month}; "
                    f"{result['failed']} failed. First error: {first_error}"
                ),
                level=messages.ERROR,
            )
        else:
            self.message_user(
                request,
                f"Sent {result['sent']} monthly analysis email(s) for {month}.",
                level=messages.SUCCESS,
            )
        return redirect('admin:login_monthlyanalysismailsetting_changelist')

    def send_to_user(self, request):
        form = SendMonthlyAnalysisToUserForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
                form.add_error(None, 'SMTP is not configured for this service.')
            else:
                recipient = form.cleaned_data['recipient']
                report_month = form.cleaned_data['report_month'].strftime('%Y-%m')
                try:
                    send_monthly_analysis_email(recipient, report_month)
                except Exception:
                    form.add_error(
                        None,
                        'The report could not be sent. Check the email service settings and try again.',
                    )
                else:
                    self.message_user(
                        request,
                        f'Monthly analysis for {report_month} sent to {recipient.email}.',
                        level=messages.SUCCESS,
                    )
                    return redirect('admin:login_monthlyanalysismailsetting_changelist')

        return render(request, 'admin/login/monthlyanalysismailsetting/send_to_user.html', {
            **self.admin_site.each_context(request),
            'title': 'Send Monthly Analysis to a User',
            'form': form,
            'opts': self.model._meta,
        })


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
