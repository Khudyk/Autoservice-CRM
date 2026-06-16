"""Представлення (views) для клієнтів."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.utils import (
    filter_queryset_by_company,
    get_object_or_404_for_company,
    get_user_company,
    paginate_queryset,
)
from clients.forms import ClientForm
from clients.models import Client
from company.models import Company
from vehicles.models import Vehicle
from workorders.models import WorkOrder

from permissions.utils import permission_required


@permission_required('clients', 'read')
def client_list(request: HttpRequest) -> HttpResponse:
    """Відображає список клієнтів з пошуком за ПІБ, телефоном або email."""
    qs = filter_queryset_by_company(
        request,
        Client.objects.select_related('company'),
    )

    # Пошук за ПІБ, телефоном, email
    search_query: str = request.GET.get('q', '').strip()
    if search_query:
        qs = qs.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    page_obj = paginate_queryset(request, qs)
    return render(request, 'clients/list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
    })


@permission_required('clients', 'read')
def client_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Відображає інформацію про клієнта, список його автомобілів та нарядів."""
    client: Client = get_object_or_404_for_company(request, Client, pk=pk)
    vehicles_qs = filter_queryset_by_company(
        request,
        Vehicle.objects.filter(client=client).select_related('company'),
    ).order_by('-created_at')
    vehicles_page = paginate_queryset(request, vehicles_qs, per_page=10)

    # Наряди клієнта
    workorders_qs = filter_queryset_by_company(
        request,
        WorkOrder.objects.filter(client=client)
        .select_related('vehicle', 'created_by__user'),
    ).order_by('-created_at')
    workorders_page = paginate_queryset(request, workorders_qs, per_page=10, page_param='wo_page')

    return render(request, 'clients/detail.html', {
        'client': client,
        'vehicles_page': vehicles_page,
        'workorders_page': workorders_page,
    })


@transaction.atomic
@permission_required('clients', 'edit')
def client_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує клієнта."""
    client: Client = get_object_or_404_for_company(request, Client, pk=pk)

    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
    else:
        form = ClientForm(instance=client)

    if form.is_valid():
        form.save()
        return redirect('client_list')

    return render(request, 'clients/form.html', {
        'form': form,
        'title': 'Редагувати клієнта',
    })


@transaction.atomic
@permission_required('clients', 'delete')
def client_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє клієнта."""
    client: Client = get_object_or_404_for_company(request, Client, pk=pk)

    if request.method == 'POST':
        client.delete()
        return redirect('client_list')
    return render(request, 'clients/confirm_delete.html', {
        'client': client,
    })


@transaction.atomic
@permission_required('clients', 'create')
def client_quick_create(request: HttpRequest) -> JsonResponse:
    """AJAX-ендпоінт для швидкого створення клієнта (з модального вікна).

    Працює тільки POST, повертає JSON з id та display.
    """
    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'errors': {'__all__': 'Дозволено тільки POST-запит.'}},
            status=405,
        )

    form = ClientForm(request.POST)

    if form.is_valid():
        company = get_user_company(request)
        if company:
            form.instance.company = company
        client: Client = form.save()
        return JsonResponse({
            'success': True,
            'id': client.pk,
            'display': str(client),
        })

    return JsonResponse({'success': False, 'errors': form.errors}, status=400)
