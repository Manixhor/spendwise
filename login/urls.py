from django.urls import path

from .views import onboarding, signup, login_view, dashboard

urlpatterns = [
    path("", onboarding, name="onboarding"),
    path("signup/", signup, name="signup"),
    path("login/", login_view, name="login"),
    path("dashboard/", dashboard, name="dashboard"),
]
