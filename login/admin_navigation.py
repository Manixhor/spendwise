from django.urls import reverse


def is_superuser(request):
    return request.user.is_active and request.user.is_superuser


def invite_user_link(request):
    return reverse('admin:auth_user_add')


def users_link(request):
    return reverse('admin:auth_user_changelist')


def analytics_link(request):
    return reverse('admin_dashboard')


def broadcast_link(request):
    return reverse('admin_broadcast')


def monthly_email_schedule_link(request):
    return reverse('admin:login_monthlyanalysismailsetting_changelist')
