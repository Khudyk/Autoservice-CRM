"""Головне представлення — дашборд системи.

Показує останні замовлення й наряди для поточної компанії.
"""

from django.shortcuts import render
from django.http import HttpRequest

from company.models import Company
from purchases.models import PurchaseOrder
from workorders.models import WorkOrder


def index(request: HttpRequest):
    """Головна сторінка — дашборд зі швидкими діями та останніми нарядами.

    Для анонімних користувачів показує спрощену сторінку.
    Для автентифікованих — останні замовлення й наряди поточної компанії.

    Args:
        request: HTTP-запит для визначення користувача та компанії.

    Returns:
        Відрендерена сторінка дашборду з контекстом.
    """
    user = request.user
    is_authenticated = user.is_authenticated

    context: dict = {}

    if is_authenticated:
        is_staff = user.is_staff or user.is_superuser

        # Визначаємо, які компанії бачить користувач
        if is_staff:
            companies = Company.objects.all()
            company_ids = list(companies.values_list('pk', flat=True))
        else:
            try:
                employee = user.employee
                company_ids = [employee.company_id]
                companies = Company.objects.filter(pk=employee.company_id)
            except AttributeError:
                company_ids = []
                companies = Company.objects.none()

        # Останні замовлення
        context['recent_orders'] = PurchaseOrder.objects.filter(
            company_id__in=company_ids,
        ).select_related('supplier', 'company').order_by('-created_at')[:5]

        # Останні наряди
        context['recent_workorders'] = WorkOrder.objects.filter(
            company_id__in=company_ids,
        ).select_related('vehicle', 'created_by__user').order_by('-created_at')[:5]

        context['companies'] = companies

    return render(request, "index.html", context)
