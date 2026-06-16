"""Представлення (views) для постачальників."""

from __future__ import annotations

from datetime import date
from typing import Any

from django.db import models
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.utils import (
    filter_queryset_by_company,
    get_object_or_404_for_company,
    get_user_company,
    paginate_queryset,
)
from purchases.models import PurchaseOrder, PurchaseOrderItem, SupplierPayment
from suppliers.forms import SupplierForm
from suppliers.models import Supplier

from permissions.utils import permission_required


@permission_required('suppliers', 'read')
def supplier_list(request: HttpRequest) -> HttpResponse:
    """Відображає список постачальників."""
    from accounts.utils import is_admin_user

    qs = Supplier.objects.select_related('company')
    if is_admin_user(request=request):
        # Адміністратори можуть фільтрувати за компанією через ?company=<pk>
        company_id: str | None = request.GET.get('company')
        if company_id:
            try:
                qs = qs.filter(company_id=int(company_id))
            except (ValueError, TypeError):
                pass
    else:
        qs = filter_queryset_by_company(request, qs)
    page_obj = paginate_queryset(request, qs)
    return render(request, 'suppliers/list.html', {
        'page_obj': page_obj,
    })


@transaction.atomic
@permission_required('suppliers', 'create')
def supplier_create(request: HttpRequest) -> HttpResponse:
    """Створює нового постачальника."""
    from accounts.utils import is_admin_user

    if request.method == 'POST':
        form = SupplierForm(request.POST)
    else:
        form = SupplierForm()

    if form.is_valid():
        if is_admin_user(request=request) and form.cleaned_data.get('company'):
            # Адміністратори можуть створювати в будь-якій компанії
            form.instance.company = form.cleaned_data['company']
        else:
            company = get_user_company(request)
            if company:
                form.instance.company = company
        supplier: Supplier = form.save()
        return redirect('supplier_list')

    return render(
        request,
        'suppliers/form.html',
        {'form': form, 'title': 'Новий постачальник'},
    )


@transaction.atomic
@permission_required('suppliers', 'edit')
def supplier_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує постачальника.

    Args:
        pk: Первинний ключ постачальника.
    """
    supplier: Supplier = get_object_or_404_for_company(request, Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
    else:
        form = SupplierForm(instance=supplier)

    if form.is_valid():
        form.save()
        return redirect('supplier_list')

    return render(
        request,
        'suppliers/form.html',
        {'form': form, 'title': 'Редагувати постачальника'},
    )


@transaction.atomic
@permission_required('suppliers', 'delete')
def supplier_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє постачальника.

    Args:
        pk: Первинний ключ постачальника.
    """
    supplier: Supplier = get_object_or_404_for_company(request, Supplier, pk=pk)
    if request.method == 'POST':
        supplier.delete()
        return redirect('supplier_list')
    return render(
        request,
        'suppliers/confirm_delete.html',
        {'supplier': supplier},
    )


@permission_required('suppliers', 'read')
def supplier_purchases(request: HttpRequest, pk: int) -> HttpResponse:
    """Відображає закупівлі та оплати постачальника в єдиному хронологічному списку.

    Закупівлі (PurchaseOrder) та оплати (SupplierPayment) постачальника
    об'єднуються в один список, відсортований за датою (created_at для
    закупівель, payment_date для оплат). Кожен тип запису має власний шаблон
    відображення: закупівлі — картка з таблицею позицій, оплати — картка
    з платіжними реквізитами.
    Підтримує фільтрацію за діапазоном дат (?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD).
    Фільтр застосовується одночасно до закупівель (created_at) і до оплат (payment_date).

    Args:
        pk: Первинний ключ постачальника.
    """
    supplier: Supplier = get_object_or_404_for_company(request, Supplier, pk=pk)

    # Фільтрація за датою
    date_from: str | None = request.GET.get('date_from')
    date_to: str | None = request.GET.get('date_to')
    filter_from: date | None = None
    filter_to: date | None = None

    qs = filter_queryset_by_company(
        request, PurchaseOrder.objects.filter(supplier=supplier),
    )

    if date_from:
        try:
            filter_from = date.fromisoformat(date_from)
            qs = qs.filter(created_at__date__gte=filter_from)
        except (ValueError, TypeError):
            filter_from = None

    if date_to:
        try:
            filter_to = date.fromisoformat(date_to)
            qs = qs.filter(created_at__date__lte=filter_to)
        except (ValueError, TypeError):
            filter_to = None

    purchases: list[PurchaseOrder] = list(
        qs
        .select_related('supplier', 'company', 'created_by__user')
        .prefetch_related(
            models.Prefetch(
                'items',
                queryset=PurchaseOrderItem.objects.select_related('part'),
            ),
        )
        .order_by('created_at')
    )

    # Отримуємо оплати постачальника
    payments_qs = filter_queryset_by_company(
        request, SupplierPayment.objects.filter(supplier=supplier),
    )

    if filter_from:
        payments_qs = payments_qs.filter(payment_date__gte=filter_from)

    if filter_to:
        payments_qs = payments_qs.filter(payment_date__lte=filter_to)

    payments_list: list[SupplierPayment] = list(
        payments_qs
        .select_related('purchase_order', 'created_by__user')
        .order_by('payment_date', 'created_at')
    )

    # Комбінуємо закупівлі та оплати в єдиний список, відсортований за датою
    combined: list[dict[str, Any]] = []

    for purchase in purchases:
        combined.append({
            'type': 'purchase',
            'sort_date': purchase.created_at.date(),
            'obj': purchase,
        })

    for payment in payments_list:
        combined.append({
            'type': 'payment',
            'sort_date': payment.payment_date,
            'obj': payment,
        })

    combined.sort(key=lambda x: x['sort_date'])

    return render(request, 'suppliers/purchases.html', {
        'supplier': supplier,
        'combined': combined,
        'purchases_count': len(purchases),
        'payments_count': len(payments_list),
        'filter_from': filter_from,
        'filter_to': filter_to,
    })
