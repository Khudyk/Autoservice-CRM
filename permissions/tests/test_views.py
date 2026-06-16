"""Тести представлень (views) додатку permissions.

Тестує сторінку керування правами доступу (permission_matrix).
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from accounts.models import Employee
from company.models import Company
from permissions.models import EmployeePermission, Module


# ----- Фікстури для авторизованих клієнтів -----


@pytest.fixture
def regular_client(client: Client, employee: Employee) -> Client:
    """Клієнт, залогінений як звичайний співробітник (не staff)."""
    employee.user.is_staff = False
    employee.user.save()
    client.login(username=employee.user.username, password='testpass123')
    return client


@pytest.fixture
def staff_client(client: Client, employee: Employee) -> Client:
    """Клієнт, залогінений як staff."""
    employee.user.is_staff = True
    employee.user.is_superuser = True
    employee.user.save()
    client.login(username=employee.user.username, password='testpass123')
    return client


# ----- Тести -----


class TestPermissionMatrixView:
    """Тести для сторінки permission_matrix."""

    def test_anonymous_redirected_to_login(
        self,
        client: Client,
    ) -> None:
        """Анонім перенаправляється на логін."""
        url = reverse('permission_matrix')
        response = client.get(url)
        assert response.status_code == 302

    def test_access_with_permission(
        self,
        regular_client: Client,
        employee: Employee,
        module_permissions_manage: Module,
    ) -> None:
        """Користувач з правом permissions_manage.edit отримує доступ."""
        EmployeePermission.objects.create(
            employee=employee,
            module=module_permissions_manage,
            can_read=True,
            can_edit=True,
        )
        url = reverse('permission_matrix')
        response = regular_client.get(url)
        assert response.status_code == 200

    def test_access_without_permission_gets_403(
        self,
        regular_client: Client,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Користувач без права permissions_manage.edit отримує 403."""
        # Створюємо інше право, щоб вимкнути backward-compat
        EmployeePermission.objects.create(
            employee=employee,
            module=module_parts,
            can_read=True,
        )
        url = reverse('permission_matrix')
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_no_permissions_denies_access(
        self,
        regular_client: Client,
    ) -> None:
        """Без жодного EmployeePermission — доступ закрито (403)."""
        url = reverse('permission_matrix')
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_selects_employee(
        self,
        regular_client: Client,
        employee: Employee,
        module_permissions_manage: Module,
    ) -> None:
        """Вибраний співробітник відображається в контексті."""
        EmployeePermission.objects.create(
            employee=employee,
            module=module_permissions_manage,
            can_read=True,
            can_edit=True,
        )
        url = reverse('permission_matrix')
        response = regular_client.get(f'{url}?employee={employee.pk}')
        assert response.status_code == 200
        assert response.context['selected_employee'] == employee

    def test_saves_permissions_on_post(
        self,
        regular_client: Client,
        employee: Employee,
        module_permissions_manage: Module,
    ) -> None:
        """POST-запит зберігає права для вибраного співробітника."""
        # Надаємо право на редагування прав перед POST
        EmployeePermission.objects.create(
            employee=employee,
            module=module_permissions_manage,
            can_read=True,
            can_edit=True,
        )
        module_parts = Module.objects.get_or_create(
            codename='parts', defaults={'name': 'Запчастини'},
        )[0]
        url = reverse('permission_matrix')
        # В POST дані включаємо ВСІ модулі, щоб _save_employee_permissions
        # не видалив право на permissions_manage (що призвело б до 403 на redirect)
        data: dict[str, str] = {
            'employee': str(employee.pk),
            f'perm_{module_parts.pk}_read': 'on',
            f'perm_{module_parts.pk}_create': 'on',
            f'perm_{module_permissions_manage.pk}_read': 'on',
            f'perm_{module_permissions_manage.pk}_edit': 'on',
        }
        response = regular_client.post(url, data, follow=True)
        assert response.status_code == 200, f'Expected 200, got {response.status_code}'
        # Перевіряємо, що права збережено
        perm = EmployeePermission.objects.get(
            employee=employee, module=module_parts,
        )
        assert perm.can_read is True
        assert perm.can_create is True
        assert perm.can_edit is False
        assert perm.can_delete is False

    def test_removes_permissions_when_all_unchecked(
        self,
        regular_client: Client,
        employee: Employee,
        module_permissions_manage: Module,
        module_parts: Module,
    ) -> None:
        """Якщо всі галочки зняті — запис прав видаляється."""
        # Спочатку створюємо право
        EmployeePermission.objects.create(
            employee=employee,
            module=module_permissions_manage,
            can_read=True,
            can_edit=True,
        )
        EmployeePermission.objects.create(
            employee=employee,
            module=module_parts,
            can_read=True,
        )
        url = reverse('permission_matrix')
        data = {
            'employee': employee.pk,
            # Не передаємо жодних perm_* — всі будуть off
        }
        response = regular_client.post(url, data)
        # POST успішно оброблено (редирект)
        assert response.status_code == 302
        # Право на parts має бути видалено
        assert EmployeePermission.objects.filter(
            employee=employee, module=module_parts,
        ).count() == 0

    def test_non_admin_sees_only_same_company_employees(
        self,
        regular_client: Client,
        employee: Employee,
        other_employee: Employee,
        other_company: Company,
        module_permissions_manage: Module,
    ) -> None:
        """Не-адмін бачить тільки співробітників своєї компанії."""
        EmployeePermission.objects.create(
            employee=employee,
            module=module_permissions_manage,
            can_read=True,
            can_edit=True,
        )
        url = reverse('permission_matrix')
        response = regular_client.get(url)
        employees_in_context = list(response.context['employees'])
        assert employee in employees_in_context
        assert other_employee not in employees_in_context

    def test_admin_sees_all_employees(
        self,
        staff_client: Client,
        employee: Employee,
        other_employee: Employee,
        company: Company,
        other_company: Company,
        module_permissions_manage: Module,
    ) -> None:
        """Адмін бачить усіх співробітників."""
        EmployeePermission.objects.create(
            employee=employee,
            module=module_permissions_manage,
            can_read=True,
            can_edit=True,
        )
        url = reverse('permission_matrix')
        response = staff_client.get(url)
        employees_in_context = list(response.context['employees'])
        assert employee in employees_in_context
        assert other_employee in employees_in_context

    def test_non_admin_cannot_access_other_company_employee(
        self,
        regular_client: Client,
        employee: Employee,
        other_employee: Employee,
        module_permissions_manage: Module,
    ) -> None:
        """Не-адмін отримує 404 при спробі редагувати працівника іншої компанії."""
        EmployeePermission.objects.create(
            employee=employee,
            module=module_permissions_manage,
            can_read=True,
            can_edit=True,
        )
        url = reverse('permission_matrix')
        response = regular_client.get(
            f'{url}?employee={other_employee.pk}',
        )
        assert response.status_code == 404

    def test_context_contains_actions(
        self,
        regular_client: Client,
        employee: Employee,
        module_permissions_manage: Module,
    ) -> None:
        """Контекст містить список дій (read, create, edit, delete)."""
        EmployeePermission.objects.create(
            employee=employee,
            module=module_permissions_manage,
            can_read=True,
            can_edit=True,
        )
        url = reverse('permission_matrix')
        response = regular_client.get(url)
        actions = response.context['actions']
        action_codenames = [a[0] for a in actions]
        assert 'read' in action_codenames
        assert 'create' in action_codenames
        assert 'edit' in action_codenames
        assert 'delete' in action_codenames
