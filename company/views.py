"""Представлення (views) для компаній з ізоляцією даних."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.utils import get_user_company, is_admin_user
from company.forms import CompanyForm
from company.models import Company


def _get_visible_companies(request: HttpRequest) -> QuerySet:
    """Повертає QuerySet компаній, доступних поточному користувачеві.

    Адміністратори бачать усі компанії, звичайні користувачі —
    тільки свою компанію (за Employee-профілем).

    Args:
        request: HTTP-запит для визначення прав користувача.

    Returns:
        QuerySet компаній, відфільтрований за правами доступу.
    """
    if is_admin_user(request=request):
        return Company.objects.all()
    user_company = get_user_company(request=request)
    if user_company is None:
        return Company.objects.none()
    return Company.objects.filter(pk=user_company.pk)


@login_required
def company_list(request: HttpRequest) -> HttpResponse:
    """Відображає список компаній з ізоляцією даних.

    Адміністратори бачать усі компанії, звичайні користувачі —
    тільки свою.

    Args:
        request: HTTP-запит для визначення прав доступу.

    Returns:
        Відрендерена сторінка зі списком компаній.
    """
    companies = _get_visible_companies(request)
    return render(request, 'company/list.html', {'companies': companies})


@login_required
def company_create(request: HttpRequest) -> HttpResponse:
    """Створює нову компанію (тільки для адміністраторів).

    Звичайні користувачі не можуть створювати компанії.
    """
    if not is_admin_user(request=request):
        raise PermissionDenied()
    form = CompanyForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('company_list')
    return render(
        request,
        'company/form.html',
        {'form': form, 'title': 'Нова компанія'},
    )


@login_required
def company_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує компанію (тільки для адміністраторів).

    Args:
        pk: Первинний ключ компанії.
    """
    if not is_admin_user(request=request):
        raise PermissionDenied()
    company = get_object_or_404(Company, pk=pk)
    form = CompanyForm(request.POST or None, instance=company)
    if form.is_valid():
        form.save()
        return redirect('company_list')
    return render(
        request,
        'company/form.html',
        {'form': form, 'title': 'Редагувати компанію'},
    )
