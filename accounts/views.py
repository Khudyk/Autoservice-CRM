"""Представлення (views) для модуля співробітників з ізоляцією даних."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.forms import EmployeeForm
from accounts.models import Employee
from accounts.utils import (
    filter_queryset_by_company,
    get_user_company,
    has_catalog_edit_permission,
    paginate_queryset,
    prepare_list_context,
)


@login_required
def employee_list(request: HttpRequest) -> HttpResponse:
    """Відображає список співробітників. Доступно адміністраторам та директорам.

    - Django staff/superuser бачать усіх співробітників з фільтром за компанією.
    - Керівники (admin/director) бачать лише співробітників своєї компанії.
    - Менеджери та механіки отримують 403.
    """
    if not has_catalog_edit_permission(request=request):
        raise PermissionDenied()
    employees_qs = Employee.objects.select_related('user', 'company')
    employees_qs, companies, selected_company = prepare_list_context(
        request, employees_qs,
    )
    page_obj = paginate_queryset(request, employees_qs)
    return render(request, 'accounts/list.html', {
        'page_obj': page_obj,
        'companies': companies,
        'selected_company': selected_company,
    })


@login_required
@transaction.atomic
def employee_create(request: HttpRequest) -> HttpResponse:
    """Створює нового співробітника разом з новим користувачем.

    Форма містить поля для створення User (username, email, password),
    після чого створюються User + Employee в одній транзакції.

    Доступно керівникам (admin/director) та Django staff/superuser.
    """
    if not has_catalog_edit_permission(request=request):
        raise PermissionDenied()
    if not request.user.is_superuser and not hasattr(request.user, 'employee'):
        raise PermissionDenied(
            'Ваш обліковий запис не має профілю співробітника. '
            'Зверніться до адміністратора системи.',
        )
    if request.method == 'POST':
        form = EmployeeForm(request.POST, user=request.user)
    else:
        form = EmployeeForm(user=request.user)

    if form.is_valid():
        # Форма сама створює User та Employee (див. EmployeeForm.save)
        form.save()
        return redirect('employee_list')

    return render(
        request,
        'accounts/form.html',
        {'form': form, 'title': 'Новий співробітник'},
    )


@login_required
@transaction.atomic
def employee_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує співробітника та його користувача.

    Args:
        pk: Первинний ключ співробітника.

    Доступно керівникам (admin/director) та Django staff/superuser.
    """
    if not has_catalog_edit_permission(request=request):
        raise PermissionDenied()

    employee: Employee = get_object_or_404(
        filter_queryset_by_company(request, Employee.objects.all()),
        pk=pk,
    )
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee, user=request.user)
    else:
        form = EmployeeForm(instance=employee, user=request.user)

    if form.is_valid():
        form.save()
        return redirect('employee_list')

    return render(
        request,
        'accounts/form.html',
        {'form': form, 'title': 'Редагувати співробітника'},
    )


@login_required
@transaction.atomic
def employee_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє співробітника.

    Args:
        pk: Первинний ключ співробітника.

    Доступно керівникам (admin/director) та Django staff/superuser.
    """
    if not has_catalog_edit_permission(request=request):
        raise PermissionDenied()

    employee: Employee = get_object_or_404(
        filter_queryset_by_company(request, Employee.objects.all()),
        pk=pk,
    )
    if request.method == 'POST':
        employee.delete()
        return redirect('employee_list')
    return render(
        request,
        'accounts/confirm_delete.html',
        {'employee': employee},
    )
