"""Представлення для керування правами доступу."""

from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from accounts.models import Employee
from accounts.utils import (
    filter_queryset_by_company,
    get_object_or_404_for_company,
    is_admin_user,
)
from permissions.models import EmployeePermission, Module
from permissions.utils import permission_required


@permission_required('permissions_manage', 'edit')
def permission_matrix(request: HttpRequest) -> HttpResponse:
    """Сторінка редагування прав конкретного співробітника.

    GET:  вибір співробітника + матриця модуль × дія.
    POST: зберігає права для вибраного співробітника.
    """
    employees = filter_queryset_by_company(
        request,
        Employee.objects.select_related('user', 'company'),
    )
    modules = Module.objects.all()
    selected_employee_pk = request.GET.get('employee') or request.POST.get('employee')

    selected_employee: Employee | None = None
    current_perms: dict[int, set[str]] = {}

    if selected_employee_pk:
        if is_admin_user(request):
            from django.shortcuts import get_object_or_404
            selected_employee = get_object_or_404(Employee, pk=selected_employee_pk)
        else:
            selected_employee = get_object_or_404_for_company(
                request, Employee, pk=selected_employee_pk,
            )
        # Поточні права співробітника: {module_pk: {actions}}
        for ep in EmployeePermission.objects.filter(employee=selected_employee).select_related('module'):
            actions = set()
            if ep.can_read:
                actions.add('read')
            if ep.can_create:
                actions.add('create')
            if ep.can_edit:
                actions.add('edit')
            if ep.can_delete:
                actions.add('delete')
            current_perms[ep.module_id] = actions

    if request.method == 'POST' and selected_employee:
        _save_employee_permissions(request, selected_employee, modules)
        messages.success(request, f'Права для {selected_employee} оновлено.')
        return redirect(f'{request.path}?employee={selected_employee.pk}')

    return render(request, 'permissions/permission_matrix.html', {
        'employees': employees,
        'modules': modules,
        'selected_employee': selected_employee,
        'current_perms': current_perms,
        'actions': [
            ('read', 'Читання', 'R'),
            ('create', 'Створення', 'C'),
            ('edit', 'Редагування', 'E'),
            ('delete', 'Видалення', 'D'),
        ],
    })


@transaction.atomic
def _save_employee_permissions(
    request: HttpRequest,
    employee: Employee,
    modules: list[Module],
) -> None:
    """Зберігає права співробітника з POST-запиту."""
    module_ids = [m.pk for m in modules]

    for module_id in module_ids:
        can_read = request.POST.get(f'perm_{module_id}_read') == 'on'
        can_create = request.POST.get(f'perm_{module_id}_create') == 'on'
        can_edit = request.POST.get(f'perm_{module_id}_edit') == 'on'
        can_delete = request.POST.get(f'perm_{module_id}_delete') == 'on'

        if not any([can_read, can_create, can_edit, can_delete]):
            EmployeePermission.objects.filter(
                employee=employee, module_id=module_id,
            ).delete()
            continue

        EmployeePermission.objects.update_or_create(
            employee=employee,
            module_id=module_id,
            defaults={
                'can_read': can_read,
                'can_create': can_create,
                'can_edit': can_edit,
                'can_delete': can_delete,
            },
        )
