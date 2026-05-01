from django.urls import path

from .views import (
    onboarding, signup, login_view, logout_view,
    dashboard, monthly, savings,
    api_add_transaction, api_delete_transaction,
    api_set_salary, api_set_target_savings,
    api_create_goal, api_update_goal, api_delete_goal, api_contribute_goal,
)

urlpatterns = [
    path('',                                    onboarding,             name='onboarding'),
    path('signup/',                             signup,                 name='signup'),
    path('login/',                              login_view,             name='login'),
    path('logout/',                             logout_view,            name='logout'),
    path('dashboard/',                          dashboard,              name='dashboard'),
    path('monthly/',                            monthly,                name='monthly'),
    path('savings/',                            savings,                name='savings'),
    # Transaction APIs
    path('api/transactions/',                   api_add_transaction,    name='api_add_transaction'),
    path('api/transactions/<int:txn_id>/delete/', api_delete_transaction, name='api_delete_transaction'),
    # Salary / target
    path('api/salary/',                         api_set_salary,         name='api_set_salary'),
    path('api/target-savings/',                 api_set_target_savings, name='api_set_target_savings'),
    # Savings Goals APIs
    path('api/goals/',                          api_create_goal,        name='api_create_goal'),
    path('api/goals/<int:goal_id>/',            api_update_goal,        name='api_update_goal'),
    path('api/goals/<int:goal_id>/delete/',     api_delete_goal,        name='api_delete_goal'),
    path('api/goals/<int:goal_id>/contribute/', api_contribute_goal,    name='api_contribute_goal'),
]
