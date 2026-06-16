"""Тести моделі Employee."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError

from accounts.models import Employee, Role
from company.models import Company


class TestEmployeeModel:
    """Тести для моделі Employee."""

    def test_employee_str_returns_full_name_and_company(
        self,
        employee: Employee,
    ) -> None:
        """Перевіряє, що __str__ повертає 'Ім'я — Компанія'."""
        expected: str = f'{employee.user.get_full_name()} — {employee.company.name}'
        assert str(employee) == expected

    def test_employee_str_uses_username_when_no_full_name(
        self,
        employee: Employee,
        roles: None,
        another_user: User,
        company: Company,
    ) -> None:
        """Перевіряє, що __str__ використовує username, якщо ім'я не заповнене."""
        emp: Employee = Employee.objects.create(
            user=another_user,
            company=company,
        )
        emp.roles.set([Role.objects.get(codename='manager')])
        expected: str = f'{another_user.username} — {company.name}'
        assert str(emp) == expected

    def test_unique_user_company_constraint(
        self,
        employee: Employee,
        roles: None,
        user: User,
        company: Company,
    ) -> None:
        """Перевіряє, що не можна створити два записи з однаковим user+company."""
        with pytest.raises(IntegrityError):
            Employee.objects.create(
                user=user,
                company=company,
            )

    def test_employee_has_roles(
        self,
        user: User,
        company: Company,
        roles: None,
    ) -> None:
        """Перевіряє, що співробітник може мати декілька ролей."""
        emp: Employee = Employee.objects.create(user=user, company=company)
        role_mechanic = Role.objects.get(codename='mechanic')
        role_manager = Role.objects.get(codename='manager')
        emp.roles.set([role_mechanic, role_manager])
        assert emp.has_role('mechanic')
        assert emp.has_role('manager')
        assert emp.has_any_role({'mechanic', 'admin'})

    def test_employee_creation_sets_timestamps(
        self,
        employee: Employee,
    ) -> None:
        """Перевіряє, що created_at та updated_at заповнюються автоматично."""
        assert employee.created_at is not None
        assert employee.updated_at is not None

    def test_employee_str_with_different_company(
        self,
        employee: Employee,
    ) -> None:
        """Перевіряє рядкове представлення з різними компаніями - це вже прокоментовано."""
        assert employee.company.name in str(employee)


