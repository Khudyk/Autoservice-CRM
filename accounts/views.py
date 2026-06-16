"""Представлення (views) для модуля співробітників."""

from __future__ import annotations

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.forms import EmployeeForm
from accounts.models import Employee
from accounts.utils import (
    filter_queryset_by_company,
    get_object_or_404_for_company,
    paginate_queryset,
)

from permissions.utils import permission_required


@permission_required('employees', 'read')
def employee_list(request: HttpRequest) -> HttpResponse:
    """Відображає список співробітників."""
    employees_qs = filter_queryset_by_company(
        request,
        Employee.objects.select_related('user', 'company'),
    )
    page_obj = paginate_queryset(request, employees_qs)
    return render(request, 'accounts/list.html', {
        'page_obj': page_obj,
    })


@transaction.atomic
@permission_required('employees', 'create')
def employee_create(request: HttpRequest) -> HttpResponse:
    """Створює нового співробітника разом з новим користувачем.

    Форма містить поля для створення User (username, email, password),
    після чого створюються User + Employee в одній транзакції.
    """
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


@transaction.atomic
@permission_required('employees', 'edit')
def employee_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує співробітника та його користувача.

    Args:
        pk: Первинний ключ співробітника.
    """
    employee: Employee = get_object_or_404_for_company(request, Employee, pk=pk)
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


@transaction.atomic
@permission_required('employees', 'delete')
def employee_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє співробітника.

    Args:
        pk: Первинний ключ співробітника.
    """
    employee: Employee = get_object_or_404_for_company(request, Employee, pk=pk)
    if request.method == 'POST':
        employee.delete()
        return redirect('employee_list')
    return render(
        request,
        'accounts/confirm_delete.html',
        {'employee': employee},
    )
