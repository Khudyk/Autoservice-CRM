"""Представлення для керування заказ-нарядами.

Включає списки, деталі, створення, редагування та видалення
заказ-нарядів з підтримкою рядків робіт та запчастин.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import F
from django.forms import BaseFormSet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

logger = logging.getLogger('autoservice')

from accounts.utils import (
    filter_queryset_by_company,
    get_object_or_404_for_company,
    get_user_company,
    paginate_queryset,
)
from workorders.forms import (
    WorkOrderForm,
    WorkOrderPartFormSet,
    WorkOrderServiceFormSet,
)
from accounts.models import Employee
from parts.models import Part, PartLot
from vehicles.models import Vehicle
from workorders.models import WorkOrder, WorkOrderPart, WorkOrderService
from workorders.services import (
    WorkOrderServiceError,
    WorkOrderServiceLogic,
)

from permissions.utils import permission_required


def _get_lot_data(request: HttpRequest) -> list[dict[str, Any]]:
    """Повертає список доступних партій для JS-фільтрації.

    Дані використовуються на клієнті для фільтрації випадаючого списку
    партій залежно від вибраної запчастини. Шаблон серіалізує цей список
    через шаблонний фільтр json_script — без подвійного кодування.

    Args:
        request: HTTP-запит для визначення компанії.

    Returns:
        Список словників, кожен має id, part_id та display.
    """
    lots_qs = filter_queryset_by_company(
        request,
        PartLot.objects.select_related(
            'part', 'purchase_item__purchase_order',
        ).filter(quantity__gt=F('quantity_used')),
    )

    return [
        {'id': lot.pk, 'part_id': lot.part_id, 'display': str(lot)}
        for lot in lots_qs
    ]


def _get_vehicle_client_map(request: HttpRequest) -> dict[str, str]:
    """Повертає {vehicle_id: client_pk} для JS-автозаповнення клієнта.

    Returns:
        Словник {str(vehicle_id): str(client_pk), ...}.
    """
    qs = filter_queryset_by_company(
        request,
        Vehicle.objects.select_related('client').exclude(client__isnull=True),
    )
    return {
        str(v.pk): str(v.client_id)  # type: ignore[union-attr]
        for v in qs
    }


def _get_part_prices(request: HttpRequest) -> dict[str, str]:
    """Повертає словник цін продажу всіх активних запчастин для JS.

    Шаблон серіалізує цей словник через шаблонний фільтр json_script
    — без подвійного кодування.

    Returns:
        Словник {part_id_str: selling_price_str, ...}.
    """
    qs = filter_queryset_by_company(
        request,
        Part.objects.filter(is_active=True),
    )
    return {
        str(pk): str(price)
        for pk, price in qs.values_list('pk', 'selling_price')
    }


@permission_required('workorders', 'read')
def workorder_list(request: HttpRequest) -> HttpResponse:
    """Сторінка зі списком заказ-нарядів.

    Підтримує фільтрацію за діапазоном дат (?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD).
    """
    # Фільтрація за датою, статусом, авто, створив
    date_from: str | None = request.GET.get('date_from')
    date_to: str | None = request.GET.get('date_to')
    filter_from: date | None = None
    filter_to: date | None = None
    filter_status: str | None = request.GET.get('status')
    filter_created_by: str | None = request.GET.get('created_by')
    search_vin: str | None = request.GET.get('search_vin')

    qs = filter_queryset_by_company(
        request,
        WorkOrder.objects.select_related(
            'company', 'vehicle', 'client', 'created_by__user',
        ),
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

    # Фільтрація за статусом
    status_choices: list[tuple[str, str]] = WorkOrder.Status.choices
    status_labels: dict[str, str] = dict(status_choices)
    filter_status_label: str | None = None
    if filter_status and filter_status in status_labels:
        filter_status_label = status_labels[filter_status]
        qs = qs.filter(status=filter_status)
    else:
        filter_status = None

    # Фільтрація за створив
    filter_created_by_name: str | None = None
    if filter_created_by:
        try:
            emp_pk = int(filter_created_by)
            emp_obj = Employee.objects.filter(pk=emp_pk).select_related('user').first()
            if emp_obj:
                filter_created_by_name = str(emp_obj)
                qs = qs.filter(created_by_id=emp_pk)
            else:
                filter_created_by = None
        except (ValueError, TypeError):
            filter_created_by = None

    # Пошук за VIN-кодом
    if search_vin:
        search_vin_clean = search_vin.strip()
        if search_vin_clean:
            qs = qs.filter(vehicle__vin_code__icontains=search_vin_clean)
        else:
            search_vin = None

    page_obj = paginate_queryset(request, qs)

    # Список працівників для випадаючого меню фільтра
    base_qs = filter_queryset_by_company(request, WorkOrder.objects.all())
    employee_list = Employee.objects.select_related('user').filter(
        pk__in=base_qs.values('created_by'),
    ).order_by('user__last_name', 'user__first_name')

    return render(request, 'workorders/list.html', {
        'page_obj': page_obj,
        'filter_from': filter_from,
        'filter_to': filter_to,
        'filter_status': filter_status,
        'filter_status_label': filter_status_label,
        'filter_created_by': filter_created_by,
        'filter_created_by_name': filter_created_by_name,
        'search_vin': search_vin,
        'valid_statuses': status_choices,
        'employee_list': employee_list,
    })


@permission_required('workorders', 'read')
def workorder_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Сторінка детального перегляду заказ-наряду.

    Args:
        pk: ID заказ-наряду.
    """
    work_order: WorkOrder = get_object_or_404_for_company(
        request,
        WorkOrder.objects.select_related(
            'company', 'vehicle__client', 'client', 'created_by__user',
        ).prefetch_related(
            'services__work_type', 'services__employee__user',
            'parts__part',
        ),
        pk=pk,
    )
    total: Any = WorkOrderServiceLogic.calculate_work_order_total(work_order)

    # Додати services та parts в контекст
    services = work_order.services.all()
    parts = work_order.parts.all()

    wo_editable: bool = work_order.is_editable
    return render(request, 'workorders/detail.html', {
        'workorder': work_order,
        'total': total,
        'services': services,
        'parts': parts,
        'wo_editable': wo_editable,
    })


@transaction.atomic
@permission_required('workorders', 'create')
def workorder_create(request: HttpRequest) -> HttpResponse:
    """Створення нового заказ-наряду з рядками робіт та запчастин."""
    user: Any = request.user
    company = get_user_company(request=request)

    if request.method == 'POST':
        form = WorkOrderForm(request.POST, user=user, company=company)
        if form.is_valid():
            work_order: WorkOrder = form.save(commit=False)

            # Автоматично встановлюємо компанію та автора з поточного користувача
            if not company:
                form.add_error(
                    None,
                    'Ваш обліковий запис не прив\'язаний до жодної компанії. '
                    'Зверніться до адміністратора.',
                )
                service_formset = WorkOrderServiceFormSet(
                    form_kwargs={'user': user, 'company': company},
                )
                part_formset = WorkOrderPartFormSet(
                    form_kwargs={'user': user, 'company': company},
                )
            else:
                work_order.company = company
                if user.is_authenticated and hasattr(user, 'employee'):
                    work_order.created_by = user.employee  # type: ignore[union-attr]

                service_formset: BaseFormSet = WorkOrderServiceFormSet(
                    request.POST,
                    instance=work_order,
                    form_kwargs={'user': user, 'company': company},
                )
                part_formset: BaseFormSet = WorkOrderPartFormSet(
                    request.POST,
                    instance=work_order,
                    form_kwargs={'user': user, 'company': company},
                )

                if service_formset.is_valid() and part_formset.is_valid():
                    try:
                        WorkOrderServiceLogic.create_work_order_with_items(
                            work_order=work_order,
                            service_formset=service_formset,
                            part_formset=part_formset,
                        )
                    except WorkOrderServiceError as e:
                        form.add_error(None, str(e))
                        return render(request, 'workorders/form.html', {
                            'form': form,
                            'service_formset': service_formset,
                            'part_formset': part_formset,
                            'title': 'Створити заказ-наряд',
                            'lot_data': _get_lot_data(request),
                            'part_prices': _get_part_prices(request),
                            'vehicle_client_map': _get_vehicle_client_map(request),
                        })

                    logger.info(
                        'WorkOrder CREATED. User: %s, WorkOrder ID: %s, Company: %s',
                        request.user, work_order.pk, work_order.company_id,
                    )
                    return redirect('workorder_detail', pk=work_order.pk)

                logger.warning(
                    'WorkOrder CREATE validation failed. User: %s, Errors (parts): %s',
                    request.user,
                    [str(e) for e in part_formset.errors if e],
                )
        else:
            service_formset = WorkOrderServiceFormSet(
                request.POST,
                form_kwargs={'user': user, 'company': company},
            )
            part_formset = WorkOrderPartFormSet(
                request.POST,
                form_kwargs={'user': user, 'company': company},
            )
    else:
        form = WorkOrderForm(user=user, company=company)
        service_formset = WorkOrderServiceFormSet(form_kwargs={'user': user, 'company': company})
        part_formset = WorkOrderPartFormSet(form_kwargs={'user': user, 'company': company})

    return render(request, 'workorders/form.html', {
        'form': form,
        'service_formset': service_formset,
        'part_formset': part_formset,
        'title': 'Створити заказ-наряд',
        'lot_data': _get_lot_data(request),
        'part_prices': _get_part_prices(request),
        'vehicle_client_map': _get_vehicle_client_map(request),
    })


@transaction.atomic
@permission_required('workorders', 'edit')
def workorder_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагування існуючого заказ-наряду.

    Args:
        pk: ID заказ-наряду.
    """
    user: Any = request.user
    company = get_user_company(request)
    work_order: WorkOrder = get_object_or_404_for_company(
        request, WorkOrder, pk=pk,
    )

    # Редагування дозволено тільки для не-термінальних статусів
    if not work_order.is_editable:
        return render(request, 'workorders/error.html', {
            'message': 'Неможливо редагувати наряд #'
                       f'{work_order.pk}, оскільки його статус '
                       f'«{work_order.get_status_display()}» є термінальним. '
                       'Створіть новий наряд для внесення змін.',
        }, status=409)

    if request.method == 'POST':
        form = WorkOrderForm(request.POST, instance=work_order, user=user, company=company)
        if form.is_valid():
            work_order = form.save(commit=False)
            service_formset: BaseFormSet = WorkOrderServiceFormSet(
                request.POST,
                instance=work_order,
                form_kwargs={'user': user, 'company': company},
            )
            part_formset: BaseFormSet = WorkOrderPartFormSet(
                request.POST,
                instance=work_order,
                form_kwargs={'user': user, 'company': company},
            )

            if service_formset.is_valid() and part_formset.is_valid():
                try:
                    WorkOrderServiceLogic.update_work_order_with_items(
                        work_order=work_order,
                        service_formset=service_formset,
                        part_formset=part_formset,
                    )
                except WorkOrderServiceError as e:
                    form.add_error(None, str(e))
                    return render(request, 'workorders/form.html', {
                        'form': form,
                        'service_formset': service_formset,
                        'part_formset': part_formset,
                        'title': 'Редагувати заказ-наряд',
                        'workorder': work_order,
                        'lot_data': _get_lot_data(request),
                        'part_prices': _get_part_prices(request),
                        'vehicle_client_map': _get_vehicle_client_map(request),
                    })

                logger.info(
                    'WorkOrder UPDATED. User: %s, WorkOrder ID: %s, Company: %s',
                    request.user, work_order.pk, work_order.company_id,
                )
                return redirect('workorder_detail', pk=work_order.pk)

            logger.warning(
                'WorkOrder UPDATE validation failed. User: %s, WorkOrder ID: %s, Errors (parts): %s',
                request.user, work_order.pk,
                [str(e) for e in part_formset.errors if e],
            )
        else:
            service_formset = WorkOrderServiceFormSet(
                request.POST,
                instance=work_order,
                form_kwargs={'user': user, 'company': company},
            )
            part_formset = WorkOrderPartFormSet(
                request.POST,
                instance=work_order,
                form_kwargs={'user': user, 'company': company},
            )
    else:
        form = WorkOrderForm(instance=work_order, user=user, company=company)
        service_formset = WorkOrderServiceFormSet(
            instance=work_order,
            form_kwargs={'user': user, 'company': company},
        )
        part_formset = WorkOrderPartFormSet(
            instance=work_order,
            form_kwargs={'user': user, 'company': company},
        )

    return render(request, 'workorders/form.html', {
        'form': form,
        'service_formset': service_formset,
        'part_formset': part_formset,
        'title': 'Редагувати заказ-наряд',
        'workorder': work_order,
        'lot_data': _get_lot_data(request),
        'part_prices': _get_part_prices(request),
        'vehicle_client_map': _get_vehicle_client_map(request),
    })


@transaction.atomic
@permission_required('workorders', 'delete')
def workorder_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видалення заказ-наряду з підтвердженням."""
    work_order: WorkOrder = get_object_or_404_for_company(
        request,
        WorkOrder.objects.select_for_update().prefetch_related(
            'parts__part',
        ),
        pk=pk,
    )

    # Не можна видалити наряд у термінальному статусі
    if not work_order.is_editable:
        return render(request, 'workorders/error.html', {
            'message': 'Неможливо видалити наряд #'
                       f'{work_order.pk}, оскільки його статус '
                       f'«{work_order.get_status_display()}» є термінальним.',
        }, status=409)

    if request.method == 'POST':
        # Атомарно повертаємо запчастини на склад через F() вирази
        work_order_part: WorkOrderPart
        for work_order_part in work_order.parts.all():
            Part.objects.filter(pk=work_order_part.part_id).update(
                quantity_on_hand=F('quantity_on_hand') + work_order_part.quantity,
            )
        work_order.delete()
        logger.warning(
            'WorkOrder DELETED. User: %s, WorkOrder ID: %s, Company: %s',
            request.user, work_order.pk, work_order.company_id,
        )
        return redirect('workorder_list')

    return render(request, 'workorders/confirm_delete.html', {
        'workorder': work_order,
    })
