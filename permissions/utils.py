"""Утиліти для перевірки прав доступу.

Містить:
- has_permission — перевірити чи має співробітник доступ до модуля+дії.
- get_employee_permissions — отримати всі права співробітника.
- permission_required — декоратор для FBV.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect

from accounts.models import Employee


def get_employee_permissions(employee: Employee) -> dict[str, set[str]]:
    """Повертає словник прав співробітника з EmployeePermission.

    Формат:
        {'module_codename': {'read', 'create', 'edit', 'delete'}}
    """
    from permissions.models import EmployeePermission

    result: dict[str, set[str]] = {}
    perms = EmployeePermission.objects.filter(employee=employee).select_related('module')
    for ep in perms:
        actions = set()
        if ep.can_read:
            actions.add('read')
        if ep.can_create:
            actions.add('create')
        if ep.can_edit:
            actions.add('edit')
        if ep.can_delete:
            actions.add('delete')
        if actions:
            result[ep.module.codename] = actions
    return result


def has_permission(employee: Employee, module_codename: str, action: str) -> bool:
    """Перевіряє, чи має співробітник доступ до модуля+дії.

    Args:
        employee: Співробітник.
        module_codename: Код модуля (наприклад 'companies', 'workorders').
        action: Дія ('read', 'create', 'edit', 'delete').

    Returns:
        True, якщо доступ дозволено.
    """
    from permissions.models import EmployeePermission, Module

    try:
        module = Module.objects.get(codename=module_codename)
    except Module.DoesNotExist:
        return False
    return EmployeePermission.objects.filter(
        employee=employee,
        module=module,
        **{f'can_{action}': True},
    ).exists()


def _resolve_employee(request: HttpRequest) -> Employee | None:
    """Повертає Employee для запиту або None."""
    user: User = request.user
    if not user.is_authenticated:
        return None
    return getattr(user, 'employee', None)


def permission_required(
    module_codename: str,
    action: str = 'read',
) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    """Декоратор для FBV — перевіряє доступ до модуля+дії.

    Логіка перевірки:
    0. Superuser → завжди дозволено (is_superuser=True).
    1. Анонім → редирект на логін.
    2. Аутентифікований без Employee → 403 (немає профілю співробітника).
    3. Аутентифікований з Employee:
       - Перевіряється EmployeePermission для модуля+дії.
       - Якщо права немає або жодного EmployeePermission не налаштовано — 403.

    Args:
        module_codename: Код модуля (наприклад 'companies', 'workorders').
        action: Дія ('read', 'create', 'edit', 'delete').

    Використання:
        @permission_required('parts', 'edit')
        def part_update(request, pk):
            ...
    """
    def decorator(
        view_func: Callable[..., HttpResponse],
    ) -> Callable[..., HttpResponse]:
        @wraps(view_func)
        def _wrapped_view(
            request: HttpRequest, *args: Any, **kwargs: Any,
        ) -> HttpResponse:
            # Superuser має повний доступ до всього
            if request.user.is_authenticated and request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            employee: Employee | None = _resolve_employee(request)
            if employee is None:
                if request.user.is_authenticated:
                    return HttpResponseForbidden(
                        'Ваш обліковий запис не прив\'язаний до жодного співробітника. '
                        'Зверніться до адміністратора.',
                    )
                return redirect('login')
            if not has_permission(employee, module_codename, action):
                return HttpResponseForbidden(
                    f'Відсутні права на дію "{action}" для модуля "{module_codename}".',
                )
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
