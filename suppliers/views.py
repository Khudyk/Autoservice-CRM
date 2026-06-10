"""Представлення (views) для постачальників з ізоляцією даних."""

from __future__ import annotations

from datetime import date
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.utils import (
    filter_queryset_by_company,
    get_user_company,
    has_catalog_edit_permission,
    has_purchase_permission,
    is_admin_user,
    paginate_queryset,
    prepare_list_context,
)
from company.models import Company
from purchases.models import PurchaseOrder, PurchaseOrderItem, SupplierPayment
from suppliers.forms import SupplierForm
from suppliers.models import Supplier


@login_required
def supplier_list(request: HttpRequest) -> HttpResponse:
    """Відображає список постачальників з ізоляцією за компанією.

    - Адміністратори бачать усіх постачальників (з фільтром за компанією).
    - Звичайні користувачі — тільки постачальників своєї компанії.
    """
    qs = Supplier.objects.select_related('company')
    qs, companies, selected_company = prepare_list_context(request, qs)
    page_obj = paginate_queryset(request, qs)
    can_edit: bool = has_catalog_edit_permission(request=request)
    return render(request, 'suppliers/list.html', {
        'page_obj': page_obj,
        'companies': companies,
        'selected_company': selected_company,
        'can_edit': can_edit,
    })


@login_required
@transaction.atomic
def supplier_create(request: HttpRequest) -> HttpResponse:
    """Створює нового постачальника.

    - Адміністратори можуть вибрати будь-яку компанію.
    - Звичайні користувачі, які мають право редагувати довідники,
      створюють постачальника тільки у своїй компанії.

    Raises:
        PermissionDenied: Якщо користувач не має права редагувати
            довідники (тільки директори та адміністратори).
    """
    if not has_catalog_edit_permission(request=request):
        raise PermissionDenied(
            'Створювати постачальників можуть лише директори та адміністратори.',
        )

    if request.method == 'POST':
        form = SupplierForm(request.POST)
    else:
        form = SupplierForm()

    if not is_admin_user(request=request):
        user_company: Company | None = get_user_company(request=request)
        if user_company:
            form.fields['company'].queryset = Company.objects.filter(
                pk=user_company.pk,
            )
            form.fields['company'].initial = user_company.pk
            form.fields['company'].disabled = True

    if form.is_valid():
        supplier: Supplier = form.save()
        return redirect('supplier_list')

    return render(
        request,
        'suppliers/form.html',
        {'form': form, 'title': 'Новий постачальник'},
    )


@login_required
@transaction.atomic
def supplier_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує постачальника.

    Args:
        pk: Первинний ключ постачальника.

    Raises:
        PermissionDenied: Якщо користувач не має права редагувати
            довідники (тільки директори та адміністратори).

    Якщо постачальник не належить до компанії користувача — 404.
    """
    if not has_catalog_edit_permission(request=request):
        raise PermissionDenied(
            'Редагувати постачальників можуть лише директори та адміністратори.',
        )

    supplier: Supplier = get_object_or_404(
        filter_queryset_by_company(request, Supplier.objects.all()),
        pk=pk,
    )
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
    else:
        form = SupplierForm(instance=supplier)

    if not is_admin_user(request=request):
        form.fields['company'].disabled = True

    if form.is_valid():
        form.save()
        return redirect('supplier_list')

    return render(
        request,
        'suppliers/form.html',
        {'form': form, 'title': 'Редагувати постачальника'},
    )


@login_required
@transaction.atomic
def supplier_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє постачальника з перевіркою доступу до компанії.

    Args:
        pk: Первинний ключ постачальника.

    Raises:
        PermissionDenied: Якщо користувач не має права видаляти
            довідники (тільки директори та адміністратори).
    """
    if not has_catalog_edit_permission(request=request):
        raise PermissionDenied(
            'Видаляти постачальників можуть лише директори та адміністратори.',
        )

    supplier: Supplier = get_object_or_404(
        filter_queryset_by_company(request, Supplier.objects.all()),
        pk=pk,
    )
    if request.method == 'POST':
        supplier.delete()
        return redirect('supplier_list')
    return render(
        request,
        'suppliers/confirm_delete.html',
        {'supplier': supplier},
    )


@login_required
def supplier_purchases(request: HttpRequest, pk: int) -> HttpResponse:
    """Відображає закупівлі та оплати постачальника в єдиному хронологічному списку.

    Закупівлі (PurchaseOrder) та оплати (SupplierPayment) постачальника
    об'єднуються в один список, відсортований за датою (created_at для
    закупівель, payment_date для оплат). Кожен тип запису має власний шаблон
    відображення: закупівлі — картка з таблицею позицій, оплати — картка
    з платіжними реквізитами.
    Доступ до перегляду регулюється через has_purchase_permission.
    Підтримує фільтрацію за діапазоном дат (?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD).
    Фільтр застосовується одночасно до закупівель (created_at) і до оплат (payment_date).

    Args:
        pk: Первинний ключ постачальника.

    Raises:
        PermissionDenied: Якщо користувач не має права перегляду закупівель.
    """
    if not has_purchase_permission(request=request):
        raise PermissionDenied(
            'Перегляд закупівель доступний лише директорам, адміністраторам, '
            'менеджерам, закупівельникам та складовщикам.',
        )

    supplier: Supplier = get_object_or_404(
        filter_queryset_by_company(request, Supplier.objects.all()),
        pk=pk,
    )

    # Фільтрація за датою
    date_from: str | None = request.GET.get('date_from')
    date_to: str | None = request.GET.get('date_to')
    filter_from: date | None = None
    filter_to: date | None = None

    qs = PurchaseOrder.objects.filter(supplier=supplier)

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
    payments_qs = SupplierPayment.objects.filter(supplier=supplier)

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
