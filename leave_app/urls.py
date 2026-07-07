from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/',  views.user_login,  name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('',        views.dashboard_redirect, name='dashboard_redirect'),

    # Employee
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('employee/apply/',     views.apply_leave,        name='apply_leave'),
    path('employee/leaves/',    views.my_leaves,          name='my_leaves'),

    # Manager
    path('manager/dashboard/',       views.manager_dashboard, name='manager_dashboard'),
    path('manager/review/<int:pk>/', views.manager_review,    name='manager_review'),

    # HR
    path('hr/dashboard/',          views.hr_dashboard,  name='hr_dashboard'),
    path('hr/review/<int:pk>/',    views.hr_review,     name='hr_review'),
    path('hr/add-employee/',       views.add_employee,  name='add_employee'),

    # Boss
    path('boss/dashboard/',        views.boss_dashboard, name='boss_dashboard'),
    path('boss/review/<int:pk>/',  views.hr_review,      name='boss_review'),
]
