"""Представлення (views) для компаній."""

from __future__ import annotations

from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.utils import (
    filter_queryset_by_company,
    get_object_or_404_for_company,
    is_admin_user,
)
from company.forms import CompanyForm
from company.models import Company

from permissions.utils import permission_required


@permission_required('companies', 'read')
def company_list(request: HttpRequest) -> HttpResponse:
    """Відображає список компаній.

    Адміністратори бачать усі компанії, звичайні користувачі — тільки свою.
    """
    if is_admin_user(request):
        companies = Company.objects.all()
    else:
        companies = filter_queryset_by_company(
            request, Company.objects.all(), field='pk',
        )
    return render(request, 'company/list.html', {'companies': companies})


@permission_required('companies', 'create')
def company_create(request: HttpRequest) -> HttpResponse:
    """Створює нову компанію."""
    form = CompanyForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('company_list')
    return render(
        request,
        'company/form.html',
        {'form': form, 'title': 'Нова компанія'},
    )


@permission_required('companies', 'edit')
def company_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує компанію.

    Args:
        pk: Первинний ключ компанії.
    """
    if is_admin_user(request):
        company = get_object_or_404(Company, pk=pk)
    else:
        company = get_object_or_404_for_company(request, Company, pk=pk)
    form = CompanyForm(request.POST or None, instance=company)
    if form.is_valid():
        form.save()
        return redirect('company_list')
    return render(
        request,
        'company/form.html',
        {'form': form, 'title': 'Редагувати компанію'},
    )
