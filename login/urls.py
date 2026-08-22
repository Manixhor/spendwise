from django.urls import path

from .views import (
    onboarding,
    signup,
    signup_verify,
    login_view,
    # login_otp,            # TODO: enable when OTP login is ready
    # login_otp_verify,     # TODO: enable when OTP login is ready
    logout_view,
    forgot_password,
    forgot_password_verify,
    forgot_password_reset,
    dashboard,
    lend,
    monthly,
    savings,
    profile_view,
    api_email_monthly_analysis,
    api_export_monthly_pdf,
    api_export_monthly_csv,
    api_export_monthly_xlsx,
    api_add_transaction,
    api_delete_transaction,
    api_mark_lend_paid,
    api_update_transaction,
    api_set_salary,
    api_set_currency,
    api_excess_income,
    api_set_target_savings,
    api_dashboard_summary,
    api_expenses_by_date,
    api_dad_joke,
    api_motivation_message,
    api_motivation_quote,
    api_create_goal,
    api_update_goal,
    api_delete_goal,
    api_contribute_goal,
    api_goal_allocations,
)

urlpatterns = [
    path("", onboarding, name="onboarding"),
    path("signup/", signup, name="signup"),
    path("signup/verify/", signup_verify, name="signup_verify"),
    path("login/", login_view, name="login"),
    # path("login/otp/", login_otp, name="login_otp"),            # TODO: enable when OTP login is ready
    # path("login/otp/verify/", login_otp_verify, name="login_otp_verify"),  # TODO: enable when OTP login is ready
    path("logout/", logout_view, name="logout"),
    path("forgot-password/", forgot_password, name="forgot_password"),
    path("forgot-password/verify/", forgot_password_verify, name="forgot_password_verify"),
    path("forgot-password/reset/", forgot_password_reset, name="forgot_password_reset"),
    path("dashboard/", dashboard, name="dashboard"),
    path("monthly/", monthly, name="monthly"),
    path("lend/", lend, name="lend"),
    path(
        "monthly/email/",
        api_email_monthly_analysis,
        name="api_email_monthly_analysis",
    ),
    path("monthly/export/pdf/", api_export_monthly_pdf, name="api_export_monthly_pdf"),
    path("monthly/export/csv/", api_export_monthly_csv, name="api_export_monthly_csv"),
    path("monthly/export/xlsx/", api_export_monthly_xlsx, name="api_export_monthly_xlsx"),
    path("savings/", savings, name="savings"),
    path("profile/", profile_view, name="profile"),
    # Transaction APIs
    path("api/transactions/", api_add_transaction, name="api_add_transaction"),
    path(
        "api/transactions/<int:txn_id>/update/",
        api_update_transaction,
        name="api_update_transaction",
    ),
    path(
        "api/transactions/<int:txn_id>/delete/",
        api_delete_transaction,
        name="api_delete_transaction",
    ),
    path(
        "api/transactions/<int:txn_id>/mark-paid/",
        api_mark_lend_paid,
        name="api_mark_lend_paid",
    ),
    # Salary / target / currency
    path("api/currency/", api_set_currency, name="api_set_currency"),
    path("api/salary/", api_set_salary, name="api_set_salary"),
    path("api/excess-income/", api_excess_income, name="api_excess_income"),
    path("api/target-savings/", api_set_target_savings, name="api_set_target_savings"),
    path("api/dashboard/summary/", api_dashboard_summary, name="api_dashboard_summary"),
    path("api/expenses-by-date/", api_expenses_by_date, name="api_expenses_by_date"),
    path("api/dad-joke/", api_dad_joke, name="api_dad_joke"),
    path(
        "api/motivation-message/", api_motivation_message, name="api_motivation_message"
    ),
    path("api/motivation-quote/", api_motivation_quote, name="api_motivation_quote"),
    # Savings Goals APIs
    path("api/goals/", api_create_goal, name="api_create_goal"),
    path("api/goals/<int:goal_id>/", api_update_goal, name="api_update_goal"),
    path("api/goals/<int:goal_id>/delete/", api_delete_goal, name="api_delete_goal"),
    path(
        "api/goals/<int:goal_id>/contribute/",
        api_contribute_goal,
        name="api_contribute_goal",
    ),
    path("api/goals/allocations/", api_goal_allocations, name="api_goal_allocations"),

]
