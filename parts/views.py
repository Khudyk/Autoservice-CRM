"""Представлення (views) для запчастин."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.utils import (
    filter_queryset_by_company,
    get_object_or_404_for_company,
    get_user_company,
    paginate_queryset,
)
from parts.forms import PartForm
from parts.models import Part
from purchases.models import PurchaseOrderItem
from workorders.models import WorkOrderPart

from permissions.utils import permission_required


@permission_required('parts', 'read')
def part_list(request: HttpRequest) -> HttpResponse:
    """Відображає список запчастин."""
    from accounts.utils import is_admin_user

    qs = Part.objects.select_related('company')
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
    return render(request, 'parts/list.html', {
        'page_obj': page_obj,
    })


@transaction.atomic
@permission_required('parts', 'create')
def part_create(request: HttpRequest) -> HttpResponse:
    """Створює нову запчастину."""
    from accounts.utils import is_admin_user

    if request.method == 'POST':
        form = PartForm(request.POST)
    else:
        form = PartForm()

    if form.is_valid():
        if is_admin_user(request=request) and form.cleaned_data.get('company'):
            # Адміністратори можуть створювати в будь-якій компанії
            form.instance.company = form.cleaned_data['company']
        else:
            company = get_user_company(request)
            if company:
                form.instance.company = company
        part: Part = form.save()
        return redirect('part_list')

    return render(
        request,
        'parts/form.html',
        {'form': form, 'title': 'Нова запчастина'},
    )


@transaction.atomic
@permission_required('parts', 'edit')
def part_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує запчастину.

    Args:
        pk: Первинний ключ запчастини.

    **Бізнес-логіка:**
    - Якщо на запчастину є прихідні накладні (has_purchase_orders):
      * Заборонено змінювати назву (`name`), артикул (`part_number`),
        виробника (`manufacturer`) та одиницю виміру (`unit`).
      * Продажна ціна та інші поля залишаються доступними.
    """
    part: Part = get_object_or_404_for_company(request, Part, pk=pk)

    has_purchase_orders: bool = part.has_purchase_orders

    form_kwargs: dict[str, Any] = {
        'instance': part,
    }

    if has_purchase_orders:
        form_kwargs['disable_identity_fields'] = True

    if request.method == 'POST':
        form = PartForm(request.POST, **form_kwargs)
    else:
        form = PartForm(**form_kwargs)

    if form.is_valid():
        form.save()
        return redirect('part_list')

    return render(
        request,
        'parts/form.html',
        {'form': form, 'title': 'Редагувати запчастину'},
    )


@transaction.atomic
@permission_required('parts', 'delete')
def part_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє запчастину.

    Якщо на запчастину є прихідні накладні (PurchaseOrderItem),
    видалення заборонено — повертається сторінка з помилкою.

    Args:
        pk: Первинний ключ запчастини.
    """
    part: Part = get_object_or_404_for_company(request, Part, pk=pk)

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


@permission_required('parts', 'read')
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
    part: Part = get_object_or_404_for_company(request, Part, pk=pk)

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
