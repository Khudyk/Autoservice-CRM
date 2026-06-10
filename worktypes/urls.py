"""URL-маршрути для додатку worktypes."""

from django.urls import path

from worktypes.views import (
    worktype_create,
    worktype_delete,
    worktype_list,
    worktype_update,
)

urlpatterns = [
    path('', worktype_list, name='worktype_list'),
    path('create/', worktype_create, name='worktype_create'),
    path('<int:pk>/edit/', worktype_update, name='worktype_update'),
    path('<int:pk>/delete/', worktype_delete, name='worktype_delete'),
]
