"""Представлення (views) для автомобілів."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from accounts.utils import (
    filter_queryset_by_company,
    get_object_or_404_for_company,
    get_user_company,
    paginate_queryset,
)
from company.models import Company
from vehicles.forms import VehicleForm
from vehicles.models import Vehicle
from workorders.models import WorkOrder

from permissions.utils import permission_required


@permission_required('vehicles', 'read')
def vehicle_list(request: HttpRequest) -> HttpResponse:
    """Відображає список автомобілів."""
    vehicles_qs = filter_queryset_by_company(
        request,
        Vehicle.objects.select_related('company', 'client'),
    ).annotate(
        has_work_orders=Exists(
            WorkOrder.objects.filter(vehicle_id=OuterRef('pk')),
        ),
    )

    # Пошук за VIN-кодом
    search_query: str = request.GET.get('q', '').strip()
    if search_query:
        vehicles_qs = vehicles_qs.filter(vin_code__icontains=search_query)

    page_obj = paginate_queryset(request, vehicles_qs)
    return render(request, 'vehicles/list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
    })


@transaction.atomic
@permission_required('vehicles', 'edit')
def vehicle_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує автомобіль.

    Args:
        pk: Первинний ключ автомобіля.

    Якщо на автомобіль є заказ-наряди — редагування технічних
    характеристик заборонено, але можна змінити власника (клієнта).
    """
    vehicle: Vehicle = get_object_or_404_for_company(request, Vehicle, pk=pk)

    has_work_orders: bool = vehicle.work_orders.exists()
    company = get_user_company(request)

    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=vehicle, company=company)
    else:
        form = VehicleForm(instance=vehicle, company=company)

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


@transaction.atomic
@permission_required('vehicles', 'read')
def vehicle_workorders(request: HttpRequest, pk: int) -> HttpResponse:
    """Сторінка зі списком усіх заказ-нарядів для автомобіля.

    Args:
        pk: ID автомобіля.
    """
    vehicle: Vehicle = get_object_or_404_for_company(request, Vehicle, pk=pk)

    qs = filter_queryset_by_company(
        request,
        WorkOrder.objects.filter(vehicle=vehicle).select_related(
            'company', 'created_by__user',
        ),
    )
    page_obj = paginate_queryset(request, qs)

    return render(request, 'vehicles/workorders.html', {
        'page_obj': page_obj,
        'vehicle': vehicle,
    })


@transaction.atomic
@permission_required('vehicles', 'delete')
def vehicle_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє автомобіль.

    Args:
        pk: Первинний ключ автомобіля.

    Якщо на автомобіль є заказ-наряди — видалення заборонено,
    повертається сторінка з помилкою.
    """
    vehicle: Vehicle = get_object_or_404_for_company(request, Vehicle, pk=pk)

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


@transaction.atomic
@permission_required('vehicles', 'create')
def vehicle_quick_create(request: HttpRequest) -> JsonResponse:
    """AJAX-ендпоінт для швидкого створення автомобіля (з модального вікна).

    Працює тільки POST, повертає JSON з id та display.
    """
    from accounts.utils import is_admin_user

    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'errors': {'__all__': 'Дозволено тільки POST-запит.'}},
            status=405,
        )

    form = VehicleForm(request.POST)

    if is_admin_user(request=request):
        # Адміністратори можуть вказати компанію в POST, або використовуємо їхню
        if not request.POST.get('company'):
            user_company = get_user_company(request)
            if user_company:
                form.data = form.data.copy()
                form.data['company'] = str(user_company.pk)
    else:
        # Звичайні користувачі — тільки своя компанія
        user_company = get_user_company(request)
        if user_company:
            form.fields['company'].queryset = Company.objects.filter(pk=user_company.pk)
            form.fields['company'].initial = user_company.pk
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
