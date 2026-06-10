"""URL-маршрути для додатку purchases."""

from django.urls import path

from purchases.views import (
    purchase_cancel,
    purchase_create,
    purchase_delete,
    purchase_detail,
    purchase_list,
    purchase_receive,
    purchase_submit,
    purchase_update,
    payment_create,
    payment_delete,
    payment_list,
    payment_update,
)

urlpatterns = [
    path('', purchase_list, name='purchase_list'),
    path('create/', purchase_create, name='purchase_create'),
    path('<int:pk>/', purchase_detail, name='purchase_detail'),
    path('<int:pk>/edit/', purchase_update, name='purchase_update'),
    path('<int:pk>/submit/', purchase_submit, name='purchase_submit'),
    path('<int:pk>/receive/', purchase_receive, name='purchase_receive'),
    path('<int:pk>/cancel/', purchase_cancel, name='purchase_cancel'),
    path('<int:pk>/delete/', purchase_delete, name='purchase_delete'),
    # Платежі постачальникам
    path('payments/', payment_list, name='payment_list'),
    path('payments/create/', payment_create, name='payment_create'),
    path('payments/<int:pk>/edit/', payment_update, name='payment_update'),
    path('payments/<int:pk>/delete/', payment_delete, name='payment_delete'),
]
