"""Представлення (views) для клієнтів з ізоляцією даних."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.utils import (
    filter_queryset_by_company,
    get_user_company,
    has_client_edit_permission,
    is_admin_user,
    paginate_queryset,
    prepare_list_context,
)
from clients.forms import ClientForm
from clients.models import Client
from company.models import Company
from vehicles.models import Vehicle


@login_required
def client_list(request: HttpRequest) -> HttpResponse:
    """Відображає список клієнтів з ізоляцією за компанією."""
    qs = Client.objects.select_related('company')
    qs, companies, selected_company = prepare_list_context(request, qs)
    page_obj = paginate_queryset(request, qs)
    can_edit: bool = has_client_edit_permission(request=request)
    return render(request, 'clients/list.html', {
        'page_obj': page_obj,
        'companies': companies,
        'selected_company': selected_company,
        'can_edit': can_edit,
    })


@login_required
def client_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Відображає інформацію про клієнта і список його автомобілів."""
    client: Client = get_object_or_404(
        filter_queryset_by_company(request, Client.objects.all()),
        pk=pk,
    )
    vehicles_qs = Vehicle.objects.filter(client=client).select_related(
        'company',
    ).order_by('-created_at')
    # Paginate vehicles list
    page_obj = paginate_queryset(request, vehicles_qs)
    return render(request, 'clients/detail.html', {
        'client': client,
        'page_obj': page_obj,
    })


@login_required
@transaction.atomic
def client_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує клієнта."""
    if not has_client_edit_permission(request=request):
        raise PermissionDenied(
            'Редагування клієнтів доступне лише адміністраторам, директорам та менеджерам.',
        )
    client: Client = get_object_or_404(
        filter_queryset_by_company(request, Client.objects.all()),
        pk=pk,
    )

    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
    else:
        form = ClientForm(instance=client)

    if not is_admin_user(request=request):
        form.fields['company'].disabled = True

    if form.is_valid():
        form.save()
        return redirect('client_list')

    return render(request, 'clients/form.html', {
        'form': form,
        'title': 'Редагувати клієнта',
    })


@login_required
@transaction.atomic
def client_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє клієнта з перевіркою доступу."""
    if not has_client_edit_permission(request=request):
        raise PermissionDenied(
            'Видалення клієнтів доступне лише адміністраторам, директорам та менеджерам.',
        )
    client: Client = get_object_or_404(
        filter_queryset_by_company(request, Client.objects.all()),
        pk=pk,
    )

    if request.method == 'POST':
        client.delete()
        return redirect('client_list')
    return render(request, 'clients/confirm_delete.html', {
        'client': client,
    })


@login_required
@transaction.atomic
def client_quick_create(request: HttpRequest) -> JsonResponse:
    """AJAX-ендпоінт для швидкого створення клієнта (з модального вікна).

    Працює тільки POST, повертає JSON з id та display.

    Raises:
        PermissionDenied: Якщо користувач не має права створювати клієнтів.
    """
    if not has_client_edit_permission(request=request):
        return JsonResponse(
            {'success': False, 'errors': {'__all__': 'Недостатньо прав для створення клієнта.'}},
            status=403,
        )

    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'errors': {'__all__': 'Дозволено тільки POST-запит.'}},
            status=405,
        )

    form = ClientForm(request.POST)

    if not is_admin_user(request=request):
        user_company: Company | None = get_user_company(request=request)
        if user_company:
            form.fields['company'].queryset = Company.objects.filter(pk=user_company.pk)
            form.fields['company'].initial = user_company.pk
            if not request.POST.get('company'):
                form.data = form.data.copy()
                form.data['company'] = str(user_company.pk)

    if form.is_valid():
        client: Client = form.save()
        return JsonResponse({
            'success': True,
            'id': client.pk,
            'display': str(client),
        })

    return JsonResponse({'success': False, 'errors': form.errors}, status=400)
