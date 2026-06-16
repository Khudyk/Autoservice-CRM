"""Представлення (views) для видів робіт."""

from __future__ import annotations

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.utils import (
    filter_queryset_by_company,
    get_object_or_404_for_company,
    get_user_company,
    paginate_queryset,
)
from worktypes.forms import WorkTypeForm
from worktypes.models import WorkType

from permissions.utils import permission_required


@permission_required('worktypes', 'read')
def worktype_list(request: HttpRequest) -> HttpResponse:
    """Відображає список видів робіт."""
    from accounts.utils import is_admin_user

    qs = WorkType.objects.select_related('company')
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
    return render(request, 'worktypes/list.html', {
        'page_obj': page_obj,
    })


@transaction.atomic
@permission_required('worktypes', 'create')
def worktype_create(request: HttpRequest) -> HttpResponse:
    """Створює новий вид роботи."""
    from accounts.utils import is_admin_user

    if request.method == 'POST':
        form = WorkTypeForm(request.POST)
    else:
        form = WorkTypeForm()

    if form.is_valid():
        if is_admin_user(request=request) and form.cleaned_data.get('company'):
            # Адміністратори можуть створювати в будь-якій компанії
            form.instance.company = form.cleaned_data['company']
        else:
            company = get_user_company(request)
            if company:
                form.instance.company = company
        worktype: WorkType = form.save()
        return redirect('worktype_list')

    return render(
        request,
        'worktypes/form.html',
        {'form': form, 'title': 'Новий вид роботи'},
    )


@transaction.atomic
@permission_required('worktypes', 'edit')
def worktype_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує вид роботи.

    Args:
        pk: Первинний ключ виду роботи.
    """
    worktype: WorkType = get_object_or_404_for_company(request, WorkType, pk=pk)
    if request.method == 'POST':
        form = WorkTypeForm(request.POST, instance=worktype)
    else:
        form = WorkTypeForm(instance=worktype)

    if form.is_valid():
        form.save()
        return redirect('worktype_list')

    return render(
        request,
        'worktypes/form.html',
        {'form': form, 'title': 'Редагувати вид роботи'},
    )


@transaction.atomic
@permission_required('worktypes', 'delete')
def worktype_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє вид роботи.

    Args:
        pk: Первинний ключ виду роботи.
    """
    worktype: WorkType = get_object_or_404_for_company(request, WorkType, pk=pk)
    if request.method == 'POST':
        worktype.delete()
        return redirect('worktype_list')
    return render(
        request,
        'worktypes/confirm_delete.html',
        {'worktype': worktype},
    )
