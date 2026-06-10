"""Тести сервісного шару EmployeeService."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.db.models import QuerySet

from accounts.models import Employee, Role
from accounts.services import EmployeeService
from company.models import Company


class TestEmployeeService:
    """Тести для EmployeeService."""

    def test_get_employees_for_company_returns_only_company_employees(
        self,
        employee: Employee,
        user: User,
        company: Company,
    ) -> None:
        """Перевіряє фільтрацію співробітників за компанією."""
        another_company: Company = Company.objects.create(name='Інша компанія')
        another_user: User = User.objects.create_user(
            username='another',
            password='pass',
        )
        Employee.objects.create(
            user=another_user,
            company=another_company,
        )

        result: QuerySet[Employee] = (
            EmployeeService.get_employees_for_company(company)
        )
        assert result.count() == 1
        assert result.first() == employee

    def test_get_employees_for_company_uses_select_related(
        self,
        employee: Employee,
        company: Company,
    ) -> None:
        """Перевіряє, що запит використовує select_related."""
        result: QuerySet[Employee] = (
            EmployeeService.get_employees_for_company(company)
        )
        query: str = str(result.query)
        assert 'INNER JOIN' in query or 'LEFT OUTER JOIN' in query

    def test_get_employee_by_id_returns_employee(
        self,
        employee: Employee,
    ) -> None:
        """Перевіряє пошук співробітника за ID."""
        result: Employee | None = EmployeeService.get_employee_by_id(employee.pk)
        assert result is not None
        assert result.pk == employee.pk

    def test_get_employee_by_id_returns_none_for_missing(
        self,
        db: None,
    ) -> None:
        """Перевіряє, що для неіснуючого ID повертається None."""
        result: Employee | None = EmployeeService.get_employee_by_id(99999)
        assert result is None

    def test_create_employee_success(
        self,
        user: User,
        company: Company,
        roles: None,
    ) -> None:
        """Перевіряє успішне створення співробітника."""
        employee: Employee = EmployeeService.create_employee(
            user=user,
            company=company,
            role='director',
            phone='+380509998877',
            parts_sale_percent=5.00,
            labor_percent=15.00,
        )
        assert employee.user == user
        assert employee.company == company
        assert employee.has_role('director')
        assert employee.phone == '+380509998877'
        assert employee.is_active is True
        assert employee.parts_sale_percent == 5.00
        assert employee.labor_percent == 15.00

    def test_create_employee_default_role(
        self,
        user: User,
        company: Company,
        roles: None,
    ) -> None:
        """Перевіряє, що роль за замовчуванням — MECHANIC."""
        employee: Employee = EmployeeService.create_employee(
            user=user,
            company=company,
        )
        assert employee.has_role('mechanic')

    def test_create_employee_default_percentages(
        self,
        user: User,
        company: Company,
        roles: None,
    ) -> None:
        """Перевіряє, що відсотки за замовчуванням дорівнюють 0.00."""
        employee: Employee = EmployeeService.create_employee(
            user=user,
            company=company,
        )
        assert employee.parts_sale_percent == 0.00
        assert employee.labor_percent == 0.00

    def test_update_employee_updates_fields(
        self,
        employee: Employee,
        roles: None,
    ) -> None:
        """Перевіряє оновлення полів співробітника."""
        updated: Employee = EmployeeService.update_employee(
            employee=employee,
            role='manager',
            phone='+380509990000',
            is_active=False,
            parts_sale_percent=7.50,
            labor_percent=20.00,
        )
        assert updated.has_role('manager')
        assert updated.phone == '+380509990000'
        assert updated.is_active is False
        assert updated.parts_sale_percent == 7.50
        assert updated.labor_percent == 20.00

    def test_update_employee_partial(
        self,
        employee: Employee,
        roles: None,
    ) -> None:
        """Перевіряє часткове оновлення — незмінні поля залишаються як є."""
        original_phone: str = employee.phone
        updated: Employee = EmployeeService.update_employee(
            employee=employee,
            role='admin',
        )
        assert updated.has_role('admin')
        assert updated.phone == original_phone
        assert updated.is_active is True
        # Відсотки не передані — мають залишитись 0.00
        assert updated.parts_sale_percent == 0.00
        assert updated.labor_percent == 0.00

    def test_update_employee_partial_percentages(
        self,
        employee: Employee,
        roles: None,
    ) -> None:
        """Перевіряє часткове оновлення тільки відсотків."""
        updated: Employee = EmployeeService.update_employee(
            employee=employee,
            parts_sale_percent=12.00,
            labor_percent=30.00,
        )
        assert updated.parts_sale_percent == 12.00
        assert updated.labor_percent == 30.00
        # Інші поля не змінилися
        assert updated.is_active is True
        assert updated.phone == employee.phone

    def test_deactivate_employee_sets_inactive(
        self,
        employee: Employee,
    ) -> None:
        """Перевіряє деактивацію співробітника."""
        deactivated: Employee = EmployeeService.deactivate_employee(employee)
        assert deactivated.is_active is False
