"""URL-маршрути для додатку clients."""

from django.urls import path

from clients.views import (
    client_delete,
    client_detail,
    client_list,
    client_quick_create,
    client_update,
)

urlpatterns = [
    path('', client_list, name='client_list'),
    path('quick-create/', client_quick_create, name='client_quick_create'),
    path('<int:pk>/', client_detail, name='client_detail'),
    path('<int:pk>/edit/', client_update, name='client_update'),
    path('<int:pk>/delete/', client_delete, name='client_delete'),
]
