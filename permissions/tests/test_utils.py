"""Тести утиліт permissions (has_permission, get_employee_permissions, permission_required)."""

from __future__ import annotations

from collections.abc import Callable
from http import HTTPStatus

import pytest
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from accounts.models import Employee
from permissions.models import EmployeePermission, Module
from permissions.utils import (
    get_employee_permissions,
    has_permission,
    permission_required,
)


class TestHasPermission:
    """Тести для has_permission."""

    def test_has_read_permission(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Перевіряє наявність права на читання."""
        EmployeePermission.objects.create(
            employee=employee, module=module_parts, can_read=True,
        )
        assert has_permission(employee, 'parts', 'read') is True

    def test_no_read_permission(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Відсутність права на читання."""
        EmployeePermission.objects.create(
            employee=employee, module=module_parts, can_create=True,
        )
        assert has_permission(employee, 'parts', 'read') is False

    def test_no_permission_record(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Немає запису EmployeePermission — доступ закрито."""
        assert has_permission(employee, 'parts', 'read') is False

    def test_nonexistent_module(
        self,
        employee: Employee,
    ) -> None:
        """Неіснуючий модуль — доступ закрито."""
        assert has_permission(employee, 'nonexistent', 'read') is False

    def test_full_permissions(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Перевіряє всі чотири дії."""
        EmployeePermission.objects.create(
            employee=employee, module=module_parts,
            can_read=True, can_create=True, can_edit=True, can_delete=True,
        )
        for action in ('read', 'create', 'edit', 'delete'):
            assert has_permission(employee, 'parts', action) is True


class TestGetEmployeePermissions:
    """Тести для get_employee_permissions."""

    def test_empty_when_no_permissions(
        self,
        employee: Employee,
    ) -> None:
        """Співробітник без прав — пустий словник."""
        result = get_employee_permissions(employee)
        assert result == {}

    def test_returns_module_actions(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Повертає словник {module_codename: {actions}}."""
        EmployeePermission.objects.create(
            employee=employee, module=module_parts,
            can_read=True, can_edit=True,
        )
        result = get_employee_permissions(employee)
        assert 'parts' in result
        assert result['parts'] == {'read', 'edit'}

    def test_multiple_modules(
        self,
        employee: Employee,
        module_parts: Module,
        module_permissions_manage: Module,
    ) -> None:
        """Працює з декількома модулями."""
        EmployeePermission.objects.create(
            employee=employee, module=module_parts, can_read=True,
        )
        EmployeePermission.objects.create(
            employee=employee, module=module_permissions_manage,
            can_read=True, can_edit=True,
        )
        result = get_employee_permissions(employee)
        assert 'parts' in result
        assert 'permissions_manage' in result
        assert result['parts'] == {'read'}
        assert result['permissions_manage'] == {'read', 'edit'}


class TestPermissionRequiredDecorator:
    """Тести для permission_required декоратора."""

    def _make_view(self, status_code: int = 200) -> Callable[..., HttpResponse]:
        """Створює просту view-функцію для тестування."""
        def view_func(request: HttpRequest) -> HttpResponse:
            return HttpResponse(status=status_code)
        return view_func

    def test_anonymous_redirected_to_login(self) -> None:
        """Анонімний користувач перенаправляється на логін."""
        decorated = permission_required('parts', 'read')(self._make_view())
        request = RequestFactory().get('/')
        request.user = type('AnonymousUser', (), {'is_authenticated': False})()
        response = decorated(request)
        assert response.status_code == HTTPStatus.FOUND  # 302 redirect

    def test_authenticated_without_employee_denied(
        self, db: None,
    ) -> None:
        """Аутентифікований без Employee отримує 403."""
        decorated = permission_required('parts', 'read')(self._make_view())
        request = RequestFactory().get('/')
        request.user = User.objects.create_user(username='no_employee')
        response = decorated(request)
        assert response.status_code == 403

    def test_has_permission_allowed(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Співробітник з правом отримує доступ."""
        EmployeePermission.objects.create(
            employee=employee, module=module_parts, can_read=True,
        )
        decorated = permission_required('parts', 'read')(self._make_view())
        request = RequestFactory().get('/')
        request.user = employee.user
        response = decorated(request)
        assert response.status_code == 200

    def test_no_permission_denied(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Співробітник без права отримує 403."""
        # Створюємо хоч якесь право, щоб вимкнути backward-compat
        EmployeePermission.objects.create(
            employee=employee, module=module_parts, can_create=True,
        )
        decorated = permission_required('parts', 'read')(self._make_view())
        request = RequestFactory().get('/')
        request.user = employee.user
        response = decorated(request)
        assert response.status_code == 403

    def test_no_permissions_at_all_denied(
        self,
        employee: Employee,
    ) -> None:
        """Без жодного EmployeePermission — доступ закрито (403)."""
        decorated = permission_required('parts', 'read')(self._make_view())
        request = RequestFactory().get('/')
        request.user = employee.user
        response = decorated(request)
        assert response.status_code == 403

    def test_different_action_denied(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Право на читання не дає права на створення."""
        EmployeePermission.objects.create(
            employee=employee, module=module_parts, can_read=True,
        )
        decorated = permission_required('parts', 'create')(self._make_view())
        request = RequestFactory().get('/')
        request.user = employee.user
        response = decorated(request)
        assert response.status_code == 403
