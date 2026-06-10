"""Представлення (views) для запчастин з ізоляцією даних."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.utils import (
    filter_queryset_by_company,
    get_user_company,
    has_catalog_edit_permission,
    has_price_edit_permission,
    is_admin_user,
    paginate_queryset,
    prepare_list_context,
)
from company.models import Company
from parts.forms import PartForm
from parts.models import Part
from purchases.models import PurchaseOrderItem
from workorders.models import WorkOrderPart


@login_required
def part_list(request: HttpRequest) -> HttpResponse:
    """Відображає список запчастин з ізоляцією за компанією.

    - Адміністратори бачать усі запчастини (з фільтром за компанією).
    - Звичайні користувачі — тільки запчастини своєї компанії.
    """
    qs = Part.objects.select_related('company')
    qs, companies, selected_company = prepare_list_context(request, qs)
    page_obj = paginate_queryset(request, qs)
    can_edit: bool = has_catalog_edit_permission(request=request)
    can_edit_price: bool = has_price_edit_permission(request=request)
    return render(request, 'parts/list.html', {
        'page_obj': page_obj,
        'companies': companies,
        'selected_company': selected_company,
        'can_edit': can_edit,
        'can_edit_price': can_edit_price,
    })


@login_required
@transaction.atomic
def part_create(request: HttpRequest) -> HttpResponse:
    """Створює нову запчастину.

    - Адміністратори можуть вибрати будь-яку компанію.
    - Звичайні користувачі, які мають право редагувати довідники,
      створюють запчастину тільки у своїй компанії.

    Raises:
        PermissionDenied: Якщо користувач не має права редагувати
            довідники (тільки директори та адміністратори).
    """
    if not has_catalog_edit_permission(request=request):
        raise PermissionDenied(
            'Створювати запчастини можуть лише директори та адміністратори.',
        )

    can_edit_price: bool = has_price_edit_permission(request=request)

    form_kwargs: dict[str, Any] = {}
    if not can_edit_price:
        form_kwargs['can_edit_price'] = False

    if request.method == 'POST':
        form = PartForm(request.POST, **form_kwargs)
    else:
        form = PartForm(**form_kwargs)

    if not is_admin_user(request=request):
        user_company: Company | None = get_user_company(request=request)
        if user_company:
            form.fields['company'].queryset = Company.objects.filter(
                pk=user_company.pk,
            )
            form.fields['company'].initial = user_company.pk
            form.fields['company'].disabled = True

    if form.is_valid():
        part: Part = form.save()
        return redirect('part_list')

    return render(
        request,
        'parts/form.html',
        {'form': form, 'title': 'Нова запчастина'},
    )


@login_required
@transaction.atomic
def part_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує запчастину.

    Args:
        pk: Первинний ключ запчастини.

    Raises:
        PermissionDenied: Якщо користувач не має права редагувати
            довідники (тільки директори та адміністратори).

    **Бізнес-логіка:**
    - Доступ мають:
      * Редактори довідників (admin/director) — можуть змінювати всі поля.
      * Редактори цін (manager/purchaser) — можуть змінювати тільки
        продажну ціну (`selling_price`).
    - Якщо запчастина не належить до компанії користувача — 404.
    - Якщо на запчастину є прихідні накладні (has_purchase_orders):
      * Заборонено змінювати назву (`name`), артикул (`part_number`),
        виробника (`manufacturer`) та одиницю виміру (`unit`).
      * Продажна ціна та інші поля залишаються доступними.
    """
    has_catalog_perm: bool = has_catalog_edit_permission(request=request)
    has_price_perm: bool = has_price_edit_permission(request=request)

    if not has_catalog_perm and not has_price_perm:
        raise PermissionDenied(
            'Редагувати запчастини можуть лише директори, адміністратори, '
            'менеджери та закупівельники.',
        )

    part: Part = get_object_or_404(
        filter_queryset_by_company(request, Part.objects.all()),
        pk=pk,
    )

    has_purchase_orders: bool = part.has_purchase_orders

    form_kwargs: dict[str, Any] = {
        'instance': part,
    }

    if has_purchase_orders:
        form_kwargs['disable_identity_fields'] = True

    # Якщо користувач не має прав редактора довідників — обмежуємо
    # редагування тільки полем продажної ціни
    only_price: bool = has_price_perm and not has_catalog_perm
    if only_price:
        form_kwargs['can_edit_price'] = True
    elif not has_price_perm:
        form_kwargs['can_edit_price'] = False

    if request.method == 'POST':
        form = PartForm(request.POST, **form_kwargs)
    else:
        form = PartForm(**form_kwargs)

    if only_price:
        # Для редакторів цін блокуємо тільки ідентифікаційні поля,
        # але дозволяємо редагувати мінімальний залишок,
        # місце на складі, активність та продажну ціну
        readonly_fields: set[str] = {
            'name', 'part_number', 'manufacturer', 'unit', 'company',
        }
        for field_name in form.fields:
            if field_name in readonly_fields:
                form.fields[field_name].disabled = True
    elif not is_admin_user(request=request):
        form.fields['company'].disabled = True

    if form.is_valid():
        form.save()
        return redirect('part_list')

    return render(
        request,
        'parts/form.html',
        {'form': form, 'title': 'Редагувати запчастину'},
    )


@login_required
@transaction.atomic
def part_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє запчастину з перевіркою доступу до компанії.

    Якщо на запчастину є прихідні накладні (PurchaseOrderItem),
    видалення заборонено — повертається сторінка з помилкою.

    Args:
        pk: Первинний ключ запчастини.

    Raises:
        PermissionDenied: Якщо користувач не має права видаляти
            довідники (тільки директори та адміністратори).
    """
    if not has_catalog_edit_permission(request=request):
        raise PermissionDenied(
            'Видаляти запчастини можуть лише директори та адміністратори.',
        )

    part: Part = get_object_or_404(
        filter_queryset_by_company(request, Part.objects.all()),
        pk=pk,
    )

    if part.has_purchase_orders:
        return render(request, 'parts/error.html', {
            'message': 'Неможливо видалити запчастину (ID: '
                       f'{part.pk}), оскільки вона використовується '
                       'в прихідних накладних. Спочатку видаліть усі '
                       'пов\'язані прихідні накладні.',
        }, status=409)

    if request.method == 'POST':
        part.delete()
        return redirect('part_list')
    return render(
        request,
        'parts/confirm_delete.html',
        {'part': part},
    )


@login_required
def part_movement(request: HttpRequest, pk: int) -> HttpResponse:
    """Відображає рух запчастини в єдиному хронологічному списку.

    Прихідні накладні (PurchaseOrderItem) та наряди використання
    (WorkOrderPart) об'єднуються в один список, відсортований
    за датою (created_at) від найновіших до найстаріших.
    Підтримує фільтрацію за діапазоном дат.

    Args:
        pk: Первинний ключ запчастини.

    **Бізнес-логіка:**
    - Показує прихідні накладні (PurchaseOrder) та заказ-наряди (WorkOrder)
      для вказаної запчастини, відфільтровані за діапазоном дат.
    - За замовчуванням показує дані за останній рік.
    - Дані сортуються від найновіших до найстаріших у єдиному списку.
    """
    part: Part = get_object_or_404(
        filter_queryset_by_company(request, Part.objects.all()),
        pk=pk,
    )

    today: datetime = timezone.now()
    default_from: datetime = today - timedelta(days=365)

    date_from_str: str = request.GET.get('date_from', '')
    date_to_str: str = request.GET.get('date_to', '')

    try:
        date_from: datetime = datetime.strptime(date_from_str, '%Y-%m-%d').replace(
            tzinfo=timezone.get_current_timezone(),
        ) if date_from_str else default_from
    except (ValueError, TypeError):
        date_from = default_from

    try:
        date_to: datetime = datetime.strptime(date_to_str, '%Y-%m-%d').replace(
            tzinfo=timezone.get_current_timezone(),
            hour=23, minute=59, second=59,
        ) if date_to_str else today
    except (ValueError, TypeError):
        date_to = today

    date_filter: Q = Q(purchase_order__created_at__gte=date_from) & Q(
        purchase_order__created_at__lte=date_to,
    )

    purchase_items = (
        PurchaseOrderItem.objects
        .filter(part=part)
        .filter(date_filter)
        .select_related('purchase_order', 'purchase_order__supplier')
        .annotate(
            received_total=ExpressionWrapper(
                F('quantity_received') * F('unit_price'),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
        )
        .order_by('-purchase_order__created_at')
    )

    work_order_parts = (
        WorkOrderPart.objects
        .filter(part=part)
        .filter(work_order__created_at__gte=date_from,
                work_order__created_at__lte=date_to)
        .select_related('work_order', 'work_order__vehicle')
        .order_by('-work_order__created_at')
    )

    # Комбінуємо прихідні накладні та наряди в єдиний список, відсортований за датою
    combined: list[dict[str, Any]] = []

    for item in purchase_items:
        combined.append({
            'type': 'purchase',
            'sort_date': item.purchase_order.created_at,
            'obj': item,
        })

    for wop in work_order_parts:
        combined.append({
            'type': 'workorder',
            'sort_date': wop.work_order.created_at,
            'obj': wop,
        })

    combined.sort(key=lambda x: x['sort_date'], reverse=True)

    return render(request, 'parts/movement.html', {
        'part': part,
        'combined': combined,
        'purchases_count': len(purchase_items),
        'workorders_count': len(work_order_parts),
        'date_from': date_from.strftime('%Y-%m-%d'),
        'date_to': date_to.strftime('%Y-%m-%d'),
    })
