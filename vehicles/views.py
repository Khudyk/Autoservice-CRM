"""Представлення (views) для автомобілів з ізоляцією даних."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.utils import (
    filter_queryset_by_company,
    get_user_company,
    has_vehicle_edit_permission,
    has_workorder_permission,
    is_admin_user,
    paginate_queryset,
    prepare_list_context,
)
from company.models import Company
from vehicles.forms import VehicleForm
from vehicles.models import Vehicle
from workorders.models import WorkOrder


@login_required
def vehicle_list(request: HttpRequest) -> HttpResponse:
    """Відображає список автомобілів з ізоляцією за компанією.

    - Адміністратори бачать усі автомобілі (з можливістю фільтру за компанією).
    - Звичайні користувачі — тільки автомобілі своєї компанії.
    """
    vehicles_qs = Vehicle.objects.select_related('company', 'client').annotate(
        has_work_orders=Exists(
            WorkOrder.objects.filter(vehicle_id=OuterRef('pk')),
        ),
    )

    # Пошук за VIN-кодом
    search_query: str = request.GET.get('q', '').strip()
    if search_query:
        vehicles_qs = vehicles_qs.filter(vin_code__icontains=search_query)

    vehicles_qs, companies, selected_company = prepare_list_context(
        request, vehicles_qs,
    )
    page_obj = paginate_queryset(request, vehicles_qs)
    return render(request, 'vehicles/list.html', {
        'page_obj': page_obj,
        'companies': companies,
        'selected_company': selected_company,
        'search_query': search_query,
    })


@login_required
@transaction.atomic
def vehicle_create(request: HttpRequest) -> HttpResponse:
    """Створює новий автомобіль.

    - Адміністратори можуть вибрати будь-яку компанію.
    - Звичайні користувачі створюють автомобіль тільки у своїй компанії.
    """
    if not has_vehicle_edit_permission(request=request):
        raise PermissionDenied(
            'Створення автомобілів доступне лише адміністраторам, директорам та менеджерам.',
        )
    if request.method == 'POST':
        form = VehicleForm(request.POST)
    else:
        form = VehicleForm()

    if not is_admin_user(request=request):
        user_company: Company | None = get_user_company(request=request)
        if user_company:
            form.fields['company'].queryset = Company.objects.filter(
                pk=user_company.pk,
            )
            form.fields['company'].initial = user_company.pk
            form.fields['company'].disabled = True

    if form.is_valid():
        vehicle: Vehicle = form.save()
        return redirect('vehicle_list')

    return render(
        request,
        'vehicles/form.html',
        {'form': form, 'title': 'Новий автомобіль'},
    )


@login_required
@transaction.atomic
def vehicle_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує автомобіль.

    Args:
        pk: Первинний ключ автомобіля.

    Якщо автомобіль не належить до компанії користувача — 404.
    Якщо на автомобіль є заказ-наряди — редагування технічних
    характеристик заборонено, але можна змінити власника (клієнта).
    """
    if not has_vehicle_edit_permission(request=request):
        raise PermissionDenied(
            'Редагування автомобілів доступне лише адміністраторам, директорам та менеджерам.',
        )
    vehicle: Vehicle = get_object_or_404(
        filter_queryset_by_company(request, Vehicle.objects.all()),
        pk=pk,
    )

    has_work_orders: bool = vehicle.work_orders.exists()

    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=vehicle)
    else:
        form = VehicleForm(instance=vehicle)

    if not is_admin_user(request=request):
        form.fields['company'].disabled = True

    # Якщо є наряди — блокуємо технічні поля, дозволяємо лише власника
    if has_work_orders:
        _readonly_fields: set[str] = {
            'vin_code', 'brand', 'model', 'year',
            'engine_type', 'engine_displacement',
        }
        for field_name in _readonly_fields:
            form.fields[field_name].disabled = True
        form.fields['client'].required = False

    if form.is_valid():
        form.save()
        return redirect('vehicle_list')

    return render(
        request,
        'vehicles/form.html',
        {
            'form': form,
            'title': 'Редагувати автомобіль',
            'has_work_orders': has_work_orders,
        },
    )


@login_required
@transaction.atomic
def vehicle_workorders(request: HttpRequest, pk: int) -> HttpResponse:
    """Сторінка зі списком усіх заказ-нарядів для автомобіля.

    Args:
        pk: ID автомобіля.

    Returns:
        Відрендерена сторінка з пагінованим списком нарядів.
    """
    vehicle: Vehicle = get_object_or_404(
        filter_queryset_by_company(request, Vehicle.objects.all()),
        pk=pk,
    )

    qs = WorkOrder.objects.filter(vehicle=vehicle).select_related(
        'company', 'created_by__user',
    )
    qs, companies, selected_company = prepare_list_context(request, qs)
    page_obj = paginate_queryset(request, qs)
    can_edit: bool = has_workorder_permission(request=request)

    return render(request, 'vehicles/workorders.html', {
        'page_obj': page_obj,
        'vehicle': vehicle,
        'can_edit': can_edit,
        'companies': companies,
        'selected_company': selected_company,
    })


@login_required
@transaction.atomic
def vehicle_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє автомобіль з перевіркою доступу до компанії.

    Args:
        pk: Первинний ключ автомобіля.

    Якщо на автомобіль є заказ-наряди — видалення заборонено,
    повертається сторінка з помилкою.
    """
    if not has_vehicle_edit_permission(request=request):
        raise PermissionDenied(
            'Видалення автомобілів доступне лише адміністраторам, директорам та менеджерам.',
        )
    vehicle: Vehicle = get_object_or_404(
        filter_queryset_by_company(request, Vehicle.objects.all()),
        pk=pk,
    )

    if vehicle.work_orders.exists():
        return render(request, 'vehicles/error.html', {
            'message': 'Неможливо видалити автомобіль (ID: '
                       f'{vehicle.pk}), оскільки на нього створені '
                       'заказ-наряди. Спочатку видаліть усі пов\'язані наряди.',
        }, status=409)

    if request.method == 'POST':
        vehicle.delete()
        return redirect('vehicle_list')
    return render(
        request,
        'vehicles/confirm_delete.html',
        {'vehicle': vehicle},
    )


@login_required
@transaction.atomic
def vehicle_quick_create(request: HttpRequest) -> JsonResponse:
    """AJAX-ендпоінт для швидкого створення автомобіля (з модального вікна).

    Працює тільки POST, повертає JSON з id та display.

    Raises:
        PermissionDenied: Якщо користувач не має права створювати автомобілі.
    """
    if not has_vehicle_edit_permission(request=request):
        return JsonResponse(
            {'success': False, 'errors': {'__all__': 'Недостатньо прав для створення автомобіля.'}},
            status=403,
        )

    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'errors': {'__all__': 'Дозволено тільки POST-запит.'}},
            status=405,
        )

    form = VehicleForm(request.POST)

    if not is_admin_user(request=request):
        user_company: Company | None = get_user_company(request=request)
        if user_company:
            form.fields['company'].queryset = Company.objects.filter(pk=user_company.pk)
            form.fields['company'].initial = user_company.pk
            # Не дизаблимо — все одно передаємо
            if not request.POST.get('company'):
                form.data = form.data.copy()
                form.data['company'] = str(user_company.pk)

    if form.is_valid():
        vehicle: Vehicle = form.save()
        return JsonResponse({
            'success': True,
            'id': vehicle.pk,
            'display': str(vehicle),
        })

    return JsonResponse({'success': False, 'errors': form.errors}, status=400)
