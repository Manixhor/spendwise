from django.urls import path

from .views import (
    onboarding,
    signup,
    login_view,
    logout_view,
    dashboard,
    monthly,
    savings,
    profile_view,
    api_add_transaction,
    api_delete_transaction,
    api_update_transaction,
    api_set_salary,
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
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("dashboard/", dashboard, name="dashboard"),
    path("monthly/", monthly, name="monthly"),
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
    # Salary / target
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
