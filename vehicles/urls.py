"""URL-маршрути для додатку vehicles."""

from django.urls import path

from vehicles.views import (
    vehicle_create,
    vehicle_delete,
    vehicle_list,
    vehicle_quick_create,
    vehicle_update,
    vehicle_workorders,
)

urlpatterns = [
    path('', vehicle_list, name='vehicle_list'),
    path('create/', vehicle_create, name='vehicle_create'),
    path('quick-create/', vehicle_quick_create, name='vehicle_quick_create'),
    path('<int:pk>/edit/', vehicle_update, name='vehicle_update'),
    path('<int:pk>/delete/', vehicle_delete, name='vehicle_delete'),
    path('<int:pk>/workorders/', vehicle_workorders, name='vehicle_workorders'),
]
