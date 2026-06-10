"""URL-маршрути для додатку parts."""

from django.urls import path

from parts.views import (
    part_create,
    part_delete,
    part_list,
    part_movement,
    part_update,
)

urlpatterns = [
    path('', part_list, name='part_list'),
    path('create/', part_create, name='part_create'),
    path('<int:pk>/edit/', part_update, name='part_update'),
    path('<int:pk>/delete/', part_delete, name='part_delete'),
    path('<int:pk>/movement/', part_movement, name='part_movement'),
]
