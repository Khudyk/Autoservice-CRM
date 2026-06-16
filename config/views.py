"""Головне представлення — дашборд системи.

Показує останні замовлення й наряди.
"""

from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

from accounts.utils import filter_queryset_by_company
from purchases.models import PurchaseOrder
from workorders.models import WorkOrder

from permissions.utils import permission_required


def page_not_found(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    """Кастомна сторінка 404 Not Found.

    Args:
        request: HTTP-запит.
        exception: Виняток Http404 (може містити повідомлення).

    Returns:
        Відрендерена сторінка 404 з дизайном проєкту.
    """
    from django.template.response import TemplateResponse
    return TemplateResponse(
        request,
        '404.html',
        {'exception': exception},
        status=404,
    )


@permission_required('dashboard', 'read')
def index(request: HttpRequest):
    """Головна сторінка — дашборд зі швидкими діями та останніми нарядами.

    Args:
        request: HTTP-запит для визначення користувача.

    Returns:
        Відрендерена сторінка дашборду з контекстом.
    """
    context: dict = {}

    context['recent_orders'] = filter_queryset_by_company(
        request,
        PurchaseOrder.objects.select_related('supplier', 'company'),
    ).order_by('-created_at')[:5]

    context['recent_workorders'] = filter_queryset_by_company(
        request,
        WorkOrder.objects.select_related('vehicle', 'created_by__user'),
    ).order_by('-created_at')[:5]

    return render(request, "index.html", context)
