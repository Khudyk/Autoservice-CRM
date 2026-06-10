"""URL-маршрути для додатку suppliers."""

from django.urls import path

from suppliers.views import (
    supplier_create,
    supplier_delete,
    supplier_list,
    supplier_purchases,
    supplier_update,
)

urlpatterns = [
    path('', supplier_list, name='supplier_list'),
    path('create/', supplier_create, name='supplier_create'),
    path('<int:pk>/purchases/', supplier_purchases, name='supplier_purchases'),
    path('<int:pk>/edit/', supplier_update, name='supplier_update'),
    path('<int:pk>/delete/', supplier_delete, name='supplier_delete'),
]
