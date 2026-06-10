"""URL-конфігурація додатку workorders."""

from __future__ import annotations

from django.urls import path

from workorders import views

urlpatterns = [
    path('', views.workorder_list, name='workorder_list'),

    path('<int:pk>/', views.workorder_detail, name='workorder_detail'),
    path('create/', views.workorder_create, name='workorder_create'),
    path('<int:pk>/edit/', views.workorder_update, name='workorder_update'),
    path('<int:pk>/delete/', views.workorder_delete, name='workorder_delete'),
    path('mechanic-salary/', views.mechanic_salary_report, name='mechanic_salary_report'),
    path('manager-salary/', views.manager_salary_report, name='manager_salary_report'),
]
