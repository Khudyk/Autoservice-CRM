"""URL-маршрути для модуля permissions."""

from __future__ import annotations

from django.urls import path

from permissions import views

urlpatterns = [
    path('', views.permission_matrix, name='permission_matrix'),
]
