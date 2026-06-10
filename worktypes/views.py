"""Представлення (views) для видів робіт з ізоляцією даних."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.utils import (
    filter_queryset_by_company,
    get_user_company,
    has_catalog_edit_permission,
    is_admin_user,
    paginate_queryset,
    prepare_list_context,
)
from company.models import Company
from worktypes.forms import WorkTypeForm
from worktypes.models import WorkType


@login_required
def worktype_list(request: HttpRequest) -> HttpResponse:
    """Відображає список видів робіт з ізоляцією за компанією.

    - Адміністратори бачать усі види робіт (з фільтром за компанією).
    - Звичайні користувачі — тільки роботи своєї компанії.
    """
    qs = WorkType.objects.select_related('company')
    qs, companies, selected_company = prepare_list_context(request, qs)
    page_obj = paginate_queryset(request, qs)
    can_edit: bool = has_catalog_edit_permission(request=request)
    return render(request, 'worktypes/list.html', {
        'page_obj': page_obj,
        'companies': companies,
        'selected_company': selected_company,
        'can_edit': can_edit,
    })


@login_required
@transaction.atomic
def worktype_create(request: HttpRequest) -> HttpResponse:
    """Створює новий вид роботи.

    - Адміністратори можуть вибрати будь-яку компанію.
    - Звичайні користувачі, які мають право редагувати довідники,
      створюють роботу тільки у своїй компанії.

    Raises:
        PermissionDenied: Якщо користувач не має права редагувати
            довідники (тільки директори та адміністратори).
    """
    if not has_catalog_edit_permission(request=request):
        raise PermissionDenied(
            'Створювати види робіт можуть лише директори та адміністратори.',
        )

    if request.method == 'POST':
        form = WorkTypeForm(request.POST)
    else:
        form = WorkTypeForm()

    if not is_admin_user(request=request):
        user_company: Company | None = get_user_company(request=request)
        if user_company:
            form.fields['company'].queryset = Company.objects.filter(
                pk=user_company.pk,
            )
            form.fields['company'].initial = user_company.pk
            form.fields['company'].disabled = True

    if form.is_valid():
        worktype: WorkType = form.save()
        return redirect('worktype_list')

    return render(
        request,
        'worktypes/form.html',
        {'form': form, 'title': 'Новий вид роботи'},
    )


@login_required
@transaction.atomic
def worktype_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує вид роботи.

    Args:
        pk: Первинний ключ виду роботи.

    Raises:
        PermissionDenied: Якщо користувач не має права редагувати
            довідники (тільки директори та адміністратори).

    Якщо робота не належить до компанії користувача — 404.
    """
    if not has_catalog_edit_permission(request=request):
        raise PermissionDenied(
            'Редагувати види робіт можуть лише директори та адміністратори.',
        )

    worktype: WorkType = get_object_or_404(
        filter_queryset_by_company(request, WorkType.objects.all()),
        pk=pk,
    )
    if request.method == 'POST':
        form = WorkTypeForm(request.POST, instance=worktype)
    else:
        form = WorkTypeForm(instance=worktype)

    if not is_admin_user(request=request):
        form.fields['company'].disabled = True

    if form.is_valid():
        form.save()
        return redirect('worktype_list')

    return render(
        request,
        'worktypes/form.html',
        {'form': form, 'title': 'Редагувати вид роботи'},
    )


@login_required
@transaction.atomic
def worktype_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє вид роботи з перевіркою доступу до компанії.

    Args:
        pk: Первинний ключ виду роботи.

    Raises:
        PermissionDenied: Якщо користувач не має права видаляти
            довідники (тільки директори та адміністратори).
    """
    if not has_catalog_edit_permission(request=request):
        raise PermissionDenied(
            'Видаляти види робіт можуть лише директори та адміністратори.',
        )

    worktype: WorkType = get_object_or_404(
        filter_queryset_by_company(request, WorkType.objects.all()),
        pk=pk,
    )
    if request.method == 'POST':
        worktype.delete()
        return redirect('worktype_list')
    return render(
        request,
        'worktypes/confirm_delete.html',
        {'worktype': worktype},
    )
