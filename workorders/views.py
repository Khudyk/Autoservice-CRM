"""Представлення для керування заказ-нарядами.

Включає списки, деталі, створення, редагування та видалення
заказ-нарядів з підтримкою рядків робіт та запчастин.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F
from django.forms import BaseFormSet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

logger = logging.getLogger('autoservice')

from accounts.utils import (
    filter_queryset_by_company, get_user_company,
    has_salary_report_permission, has_workorder_permission,
    is_admin_user, paginate_queryset, prepare_list_context,
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
    ManagerSummaryRow,
    MechanicSummaryRow,
    WorkOrderServiceError,
    WorkOrderServiceLogic,
    get_all_managers_summary,
    get_all_mechanics_summary,
)


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
    if is_admin_user(request=request):
        lots_qs = PartLot.objects.select_related(
            'part', 'purchase_item__purchase_order',
        ).filter(quantity__gt=F('quantity_used'))
    else:
        company = get_user_company(request=request)
        if company:
            lots_qs = PartLot.objects.select_related(
                'part', 'purchase_item__purchase_order',
            ).filter(company=company, quantity__gt=F('quantity_used'))
        else:
            lots_qs = PartLot.objects.none()

    return [
        {'id': lot.pk, 'part_id': lot.part_id, 'display': str(lot)}
        for lot in lots_qs
    ]


def _get_vehicle_client_map() -> dict[str, str]:
    """Повертає {vehicle_id: client_pk} для JS-автозаповнення клієнта.

    Returns:
        Словник {str(vehicle_id): str(client_pk), ...}.
    """
    qs = Vehicle.objects.select_related('client').exclude(client__isnull=True)
    return {
        str(v.pk): str(v.client_id)  # type: ignore[union-attr]
        for v in qs
    }


def _get_part_prices() -> dict[str, str]:
    """Повертає словник цін продажу всіх активних запчастин для JS.

    Шаблон серіалізує цей словник через шаблонний фільтр json_script
    — без подвійного кодування.

    Returns:
        Словник {part_id_str: selling_price_str, ...}.
    """
    return {
        str(pk): str(price)
        for pk, price in Part.objects.filter(is_active=True)
        .values_list('pk', 'selling_price')
    }


@login_required
def workorder_list(request: HttpRequest) -> HttpResponse:
    """Сторінка зі списком заказ-нарядів.

    Підтримує фільтрацію за діапазоном дат (?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD).
    Доступні наряди фільтруються за компанією користувача.
    """
    # Фільтрація за датою, статусом, авто, створив
    date_from: str | None = request.GET.get('date_from')
    date_to: str | None = request.GET.get('date_to')
    filter_from: date | None = None
    filter_to: date | None = None
    filter_status: str | None = request.GET.get('status')
    filter_created_by: str | None = request.GET.get('created_by')
    search_vin: str | None = request.GET.get('search_vin')

    qs = WorkOrder.objects.select_related(
        'company', 'vehicle', 'client', 'created_by__user',
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

    qs, companies, selected_company = prepare_list_context(request, qs)
    page_obj = paginate_queryset(request, qs)
    can_edit: bool = has_workorder_permission(request=request)

    # Список працівників для випадаючого меню фільтра
    base_qs = WorkOrder.objects.all()
    if is_admin_user(request=request):
        employee_list = Employee.objects.select_related('user').filter(
            pk__in=base_qs.values('created_by'),
        ).order_by('user__last_name', 'user__first_name')
    else:
        company = get_user_company(request=request)
        if company:
            employee_list = Employee.objects.select_related('user').filter(
                company=company, pk__in=base_qs.values('created_by'),
            ).order_by('user__last_name', 'user__first_name')
        else:
            employee_list = Employee.objects.none()

    return render(request, 'workorders/list.html', {
        'page_obj': page_obj,
        'companies': companies,
        'selected_company': selected_company,
        'can_edit': can_edit,
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


@login_required
def workorder_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Сторінка детального перегляду заказ-наряду.

    Args:
        pk: ID заказ-наряду.

    Returns:
       Відрендерена сторінка деталей.
    """
    work_order: WorkOrder = get_object_or_404(
        filter_queryset_by_company(
            request,
            WorkOrder.objects.select_related(
                'company', 'vehicle__client', 'client', 'created_by__user',
            ).prefetch_related(
                'services__work_type', 'services__employee__user',
                'parts__part',
            ),
        ),
        pk=pk,
    )
    total: Any = WorkOrderServiceLogic.calculate_work_order_total(work_order)

    # Додати services та parts в контекст (виправлення P2-01)
    services = work_order.services.all()
    parts = work_order.parts.all()

    can_edit: bool = has_workorder_permission(request=request)
    wo_editable: bool = work_order.is_editable
    return render(request, 'workorders/detail.html', {
        'workorder': work_order,
        'total': total,
        'services': services,
        'parts': parts,
        'can_edit': can_edit,
        'wo_editable': wo_editable,
    })


@login_required
@transaction.atomic
def workorder_create(request: HttpRequest) -> HttpResponse:
    """Створення нового заказ-наряду з рядками робіт та запчастин.

    Raises:
        PermissionDenied: Якщо користувач не має права створювати
            наряди (директори, адміністратори та менеджери).
    """
    if not has_workorder_permission(request=request):
        raise PermissionDenied(
            'Створювати наряди можуть лише директори, адміністратори '
            'та менеджери.',
        )

    user: Any = request.user

    if request.method == 'POST':
        form = WorkOrderForm(request.POST, user=user)
        if form.is_valid():
            work_order: WorkOrder = form.save(commit=False)

            # Автоматично встановлюємо компанію та автора з поточного користувача
            user_company = get_user_company(request=request)
            if not user_company:
                form.add_error(
                    None,
                    'Ваш обліковий запис не прив\'язаний до жодної компанії. '
                    'Зверніться до адміністратора.',
                )
                service_formset = WorkOrderServiceFormSet(
                    form_kwargs={'user': user},
                )
                part_formset = WorkOrderPartFormSet(
                    form_kwargs={'user': user},
                )
            else:
                work_order.company = user_company
                if user.is_authenticated and hasattr(user, 'employee'):
                    work_order.created_by = user.employee  # type: ignore[union-attr]

                service_formset: BaseFormSet = WorkOrderServiceFormSet(
                    request.POST,
                    instance=work_order,
                    form_kwargs={'user': user},
                )
                part_formset: BaseFormSet = WorkOrderPartFormSet(
                    request.POST,
                    instance=work_order,
                    form_kwargs={'user': user},
                )

                # Валідуємо formset тут, щоб помилки (напр. недостатньо
                # запчастин у партії) показувались користувачеві, а не
                # ховались за "Формети невалідні" із сервісу.
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
                            'part_prices': _get_part_prices(),
                            'vehicle_client_map': _get_vehicle_client_map(),
                        })

                    logger.info(
                        'WorkOrder CREATED. User: %s, WorkOrder ID: %s, Company: %s',
                        request.user, work_order.pk, work_order.company_id,
                    )
                    return redirect('workorder_detail', pk=work_order.pk)

                # Якщо formsets невалідні — не редиректимо, а показуємо форму
                # з помилками (вони вже заповнені після виклику is_valid())
                logger.warning(
                    'WorkOrder CREATE validation failed. User: %s, Errors (parts): %s',
                    request.user,
                    [str(e) for e in part_formset.errors if e],
                )
        else:
            service_formset = WorkOrderServiceFormSet(
                request.POST,
                form_kwargs={'user': user},
            )
            part_formset = WorkOrderPartFormSet(
                request.POST,
                form_kwargs={'user': user},
            )
    else:
        form = WorkOrderForm(user=user)
        service_formset = WorkOrderServiceFormSet(form_kwargs={'user': user})
        part_formset = WorkOrderPartFormSet(form_kwargs={'user': user})

    return render(request, 'workorders/form.html', {
        'form': form,
        'service_formset': service_formset,
        'part_formset': part_formset,
        'title': 'Створити заказ-наряд',
        'lot_data': _get_lot_data(request),
        'part_prices': _get_part_prices(),
        'vehicle_client_map': _get_vehicle_client_map(),
    })


@login_required
@transaction.atomic
def workorder_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагування існуючого заказ-наряду.

    Args:
        pk: ID заказ-наряду.

    Raises:
        PermissionDenied: Якщо користувач не має права редагувати
            рядки робіт і запчастин (директори, адміністратори,
            менеджери).
    """
    if not has_workorder_permission(request=request):
        raise PermissionDenied(
            'Редагувати роботи та запчастини можуть лише '
            'директори, адміністратори та менеджери.',
        )

    user: Any = request.user
    work_order: WorkOrder = get_object_or_404(
        filter_queryset_by_company(request, WorkOrder.objects.all()),
        pk=pk,
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
        form = WorkOrderForm(request.POST, instance=work_order, user=user)
        if form.is_valid():
            work_order = form.save(commit=False)
            service_formset: BaseFormSet = WorkOrderServiceFormSet(
                request.POST,
                instance=work_order,
                form_kwargs={'user': user},
            )
            part_formset: BaseFormSet = WorkOrderPartFormSet(
                request.POST,
                instance=work_order,
                form_kwargs={'user': user},
            )

            # Валідуємо formset тут, щоб помилки показувались
            # користувачеві, а не ховались за "Формети невалідні".
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
                        'part_prices': _get_part_prices(),
                        'vehicle_client_map': _get_vehicle_client_map(),
                    })

                logger.info(
                    'WorkOrder UPDATED. User: %s, WorkOrder ID: %s, Company: %s',
                    request.user, work_order.pk, work_order.company_id,
                )
                return redirect('workorder_detail', pk=work_order.pk)

            # Якщо formsets невалідні — показуємо форму з помилками
            logger.warning(
                'WorkOrder UPDATE validation failed. User: %s, WorkOrder ID: %s, Errors (parts): %s',
                request.user, work_order.pk,
                [str(e) for e in part_formset.errors if e],
            )
        else:
            service_formset = WorkOrderServiceFormSet(
                request.POST,
                instance=work_order,
                form_kwargs={'user': user},
            )
            part_formset = WorkOrderPartFormSet(
                request.POST,
                instance=work_order,
                form_kwargs={'user': user},
            )
    else:
        form = WorkOrderForm(instance=work_order, user=user)
        service_formset = WorkOrderServiceFormSet(
            instance=work_order,
            form_kwargs={'user': user},
        )
        part_formset = WorkOrderPartFormSet(
            instance=work_order,
            form_kwargs={'user': user},
        )

    return render(request, 'workorders/form.html', {
        'form': form,
        'service_formset': service_formset,
        'part_formset': part_formset,
        'title': 'Редагувати заказ-наряд',
        'workorder': work_order,
        'lot_data': _get_lot_data(request),
        'part_prices': _get_part_prices(),
        'vehicle_client_map': _get_vehicle_client_map(),
    })


@login_required
@transaction.atomic
def workorder_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видалення заказ-наряду з підтвердженням.

    Raises:
        PermissionDenied: Якщо користувач не має права видаляти наряди
            (директори, адміністратори, менеджери).
    """
    if not has_workorder_permission(request=request):
        raise PermissionDenied(
            'Видаляти наряди можуть лише директори, адміністратори '
            'та менеджери.',
        )

    work_order: WorkOrder = get_object_or_404(
        filter_queryset_by_company(
            request,
            WorkOrder.objects.select_for_update().prefetch_related(
                'parts__part',
            ),
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
        # (захист від race conditions — AGENTS.md, Архітектура)
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


@login_required
def mechanic_salary_report(request: HttpRequest) -> HttpResponse:
    """Зведений звіт по зарплаті всіх механіків за виконані роботи.

    Показує для кожного механіка кількість виконаних робіт, загальну
    вартість та нараховану суму з урахуванням labor_percent.

    Підтримує фільтрацію за діапазоном дат.

    Args:
        request: HTTP-запит з параметрами date_from, date_to.

    Returns:
        HTTP-відповідь з відрендереним шаблоном.

    Raises:
        PermissionDenied: Якщо користувач не має права переглядати
            зарплатні звіти (доступ лише в адміністратора, бухгалтера
            та директора).
    """
    if not has_salary_report_permission(request=request):
        raise PermissionDenied(
            'Переглядати зарплатні звіти можуть лише директори, '
            'адміністратори та бухгалтери.',
        )

    date_from_str: str | None = request.GET.get('date_from')
    date_to_str: str | None = request.GET.get('date_to')

    filter_from: date | None = None
    filter_to: date | None = None
    if date_from_str:
        try:
            filter_from = date.fromisoformat(date_from_str)
        except (ValueError, TypeError):
            filter_from = None
    if date_to_str:
        try:
            filter_to = date.fromisoformat(date_to_str)
        except (ValueError, TypeError):
            filter_to = None

    company = get_user_company(request)
    rows: list[MechanicSummaryRow] = get_all_mechanics_summary(
        company=company,
        date_from=filter_from,
        date_to=filter_to,
    )

    # Підсумки
    total_cost: Decimal = sum(
        (r.total_service_cost for r in rows), Decimal('0.00'),
    )
    total_earnings: Decimal = sum(
        (r.total_earnings for r in rows), Decimal('0.00'),
    )
    total_services: int = sum(r.services_count for r in rows)

    return render(request, 'workorders/mechanic_salary.html', {
        'rows': rows,
        'total_cost': total_cost,
        'total_earnings': total_earnings,
        'total_services': total_services,
        'mechanics_count': len(rows),
        'filter_from': filter_from,
        'filter_to': filter_to,
    })


@login_required
def manager_salary_report(request: HttpRequest) -> HttpResponse:
    """Зведений звіт по зарплаті всіх менеджерів.

    Показує для кожного менеджера кількість створених нарядів,
    вартість робіт, вартість запчастин та нараховані суми
    з урахуванням labor_percent та parts_sale_percent.

    Підтримує фільтрацію за діапазоном дат.

    Args:
        request: HTTP-запит з параметрами date_from, date_to.

    Returns:
        HTTP-відповідь з відрендереним шаблоном.

    Raises:
        PermissionDenied: Якщо користувач не має права переглядати
            зарплатні звіти (доступ лише в адміністратора, бухгалтера
            та директора).
    """
    if not has_salary_report_permission(request=request):
        raise PermissionDenied(
            'Переглядати зарплатні звіти можуть лише директори, '
            'адміністратори та бухгалтери.',
        )

    date_from_str: str | None = request.GET.get('date_from')
    date_to_str: str | None = request.GET.get('date_to')

    filter_from: date | None = None
    filter_to: date | None = None
    if date_from_str:
        try:
            filter_from = date.fromisoformat(date_from_str)
        except (ValueError, TypeError):
            filter_from = None
    if date_to_str:
        try:
            filter_to = date.fromisoformat(date_to_str)
        except (ValueError, TypeError):
            filter_to = None

    company = get_user_company(request)
    rows: list[ManagerSummaryRow] = get_all_managers_summary(
        company=company,
        date_from=filter_from,
        date_to=filter_to,
    )

    # Підсумки
    total_service_cost: Decimal = sum(
        (r.total_service_cost for r in rows), Decimal('0.00'),
    )
    total_parts_profit: Decimal = sum(
        (r.total_parts_profit for r in rows), Decimal('0.00'),
    )
    total_earnings: Decimal = sum(
        (r.total_earnings for r in rows), Decimal('0.00'),
    )
    total_orders: int = sum(r.orders_count for r in rows)

    return render(request, 'workorders/manager_salary.html', {
        'rows': rows,
        'total_service_cost': total_service_cost,
        'total_parts_profit': total_parts_profit,
        'total_earnings': total_earnings,
        'total_orders': total_orders,
        'managers_count': len(rows),
        'filter_from': filter_from,
        'filter_to': filter_to,
    })
