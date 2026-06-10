"""Тести для зведеного звіту по зарплаті механіків."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse_lazy

from accounts.models import Employee, Role
from company.models import Company
from vehicles.models import Vehicle
from workorders.models import WorkOrder, WorkOrderService
from workorders.services import (
    MechanicSummaryRow,
    get_all_mechanics_summary,
)
from worktypes.models import WorkType


# ──────────────────────────────────────────────
# Тести сервісу
# ──────────────────────────────────────────────


class TestGetAllMechanicsSummary:
    """Тести функції get_all_mechanics_summary."""

    def test_no_mechanics_returns_empty(
        self, db: None, company: Company,
    ) -> None:
        """Якщо немає співробітників з роллю mechanic — порожній список."""
        rows = get_all_mechanics_summary(company=company)
        assert rows == []

    def test_mechanic_with_labor_percent_zero(
        self, db: None, company: Company,
        user: User, roles: None,
    ) -> None:
        """Співробітник з роллю mechanic навіть з 0% labor_percent потрапляє у звіт."""
        mech: Employee = Employee.objects.create(
            user=user, company=company,
            labor_percent=Decimal('0.00'),
        )
        mech.roles.set([Role.objects.get(codename='mechanic')])
        rows = get_all_mechanics_summary(company=company)
        assert len(rows) == 1
        assert rows[0].total_earnings == Decimal('0.00')

    def test_without_mechanic_role_not_in_report(
        self, db: None, company: Company, user: User,
    ) -> None:
        """Співробітник без ролі mechanic не потрапляє у звіт навіть з labor_percent > 0."""
        Employee.objects.create(
            user=user, company=company,
            labor_percent=Decimal('10.00'),
        )
        rows = get_all_mechanics_summary(company=company)
        assert rows == []

    def test_single_mechanic_no_services(
        self, db: None, company: Company,
        user: User, roles: None,
    ) -> None:
        """Механік без робіт — рядок з нульовими показниками."""
        mech: Employee = Employee.objects.create(
            user=user, company=company,
            labor_percent=Decimal('10.00'),
        )
        mech.roles.set([Role.objects.get(codename='mechanic')])
        rows = get_all_mechanics_summary(company=company)
        assert len(rows) == 1
        row = rows[0]
        assert row.employee.pk == mech.pk
        assert row.labor_percent == Decimal('10.00')
        assert row.services_count == 0
        assert row.total_service_cost == Decimal('0.00')
        assert row.total_earnings == Decimal('0.00')

    def test_single_mechanic_with_services(
        self,
        db: None,
        company: Company,
        user: User,
        roles: None,
        worktype: WorkType,
        vehicle: Vehicle,
    ) -> None:
        """Один механік з однією роботою."""
        mech: Employee = Employee.objects.create(
            user=user, company=company,
            labor_percent=Decimal('10.00'),
        )
        mech.roles.set([Role.objects.get(codename='mechanic')])
        wo: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mech, vehicle=vehicle,
        )
        WorkOrderService.objects.create(
            work_order=wo, work_type=worktype,
            employee=mech,
            unit_price=Decimal('500.00'), quantity=2,
        )
        rows = get_all_mechanics_summary(company=company)
        assert len(rows) == 1
        row = rows[0]
        assert row.services_count == 1
        assert row.total_service_cost == Decimal('1000.00')  # 500 * 2
        assert row.total_earnings == Decimal('100.00')  # 1000 * 10 / 100

    def test_multiple_mechanics(
        self,
        db: None,
        company: Company,
        user: User,
        roles: None,
        worktype: WorkType,
        vehicle: Vehicle,
    ) -> None:
        """Два механіки з різними labor_percent."""
        mech1: Employee = Employee.objects.create(
            user=user, company=company,
            labor_percent=Decimal('10.00'),
        )
        mech1.roles.set([Role.objects.get(codename='mechanic')])
        # Унікальний user для другого механіка
        user2: User = User.objects.create_user(
            username='mech2_user', password='test123',
        )
        mech2: Employee = Employee.objects.create(
            user=user2, company=company,
            labor_percent=Decimal('15.00'),
        )
        mech2.roles.set([Role.objects.get(codename='mechanic')])

        wo: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mech1, vehicle=vehicle,
        )
        WorkOrderService.objects.create(
            work_order=wo, work_type=worktype,
            employee=mech1,
            unit_price=Decimal('1000.00'), quantity=1,
        )
        WorkOrderService.objects.create(
            work_order=wo, work_type=worktype,
            employee=mech2,
            unit_price=Decimal('2000.00'), quantity=1,
        )

        rows = get_all_mechanics_summary(company=company)
        assert len(rows) == 2

        m1 = next(r for r in rows if r.employee.pk == mech1.pk)
        assert m1.total_service_cost == Decimal('1000.00')
        assert m1.total_earnings == Decimal('100.00')  # 1000 * 10%

        m2 = next(r for r in rows if r.employee.pk == mech2.pk)
        assert m2.total_service_cost == Decimal('2000.00')
        assert m2.total_earnings == Decimal('300.00')  # 2000 * 15%

        # Сортовано за earnings спаданням: mech2 перший
        assert rows[0].employee.pk == mech2.pk

    def test_filter_by_date(
        self,
        db: None,
        company: Company,
        user: User,
        roles: None,
        worktype: WorkType,
        vehicle: Vehicle,
    ) -> None:
        """Фільтр за датою."""
        mech: Employee = Employee.objects.create(
            user=user, company=company,
            labor_percent=Decimal('10.00'),
        )
        mech.roles.set([Role.objects.get(codename='mechanic')])
        # Стара робота
        old_wo: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mech, vehicle=vehicle,
        )
        WorkOrder.objects.filter(pk=old_wo.pk).update(
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        WorkOrderService.objects.create(
            work_order=old_wo, work_type=worktype,
            employee=mech,
            unit_price=Decimal('500.00'), quantity=1,
        )
        # Нова робота
        new_wo: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mech, vehicle=vehicle,
        )
        WorkOrderService.objects.create(
            work_order=new_wo, work_type=worktype,
            employee=mech,
            unit_price=Decimal('1000.00'), quantity=1,
        )

        rows = get_all_mechanics_summary(
            company=company,
            date_from=date(2024, 1, 1),
            date_to=date(2024, 12, 31),
        )
        assert len(rows) == 1
        assert rows[0].services_count == 1
        assert rows[0].total_service_cost == Decimal('500.00')


# ──────────────────────────────────────────────
# Тести представлення
# ──────────────────────────────────────────────


class TestMechanicSalaryView:
    """Тести представлення mechanic_salary_report."""

    url = reverse_lazy('mechanic_salary_report')

    def test_redirect_if_anonymous(self, client: Client) -> None:
        """Анонім перенаправляється на логін."""
        resp = client.get(self.url)
        assert resp.status_code == 302
        assert 'login' in str(resp.url or '')

    def test_403_forbidden_no_permission(
        self, client: Client, user: User,
    ) -> None:
        """Звичайний користувач (без Employee) отримує 403."""
        client.force_login(user)
        resp = client.get(self.url)
        assert resp.status_code == 403

    def test_200_with_employee_role(
        self, client: Client, salary_employee: Employee,
    ) -> None:
        """Заходить якщо є співробітник з роллю director (доступ до звітів)."""
        client.force_login(salary_employee.user)
        resp = client.get(self.url)
        assert resp.status_code == 200

    def test_context_contains_rows(
        self,
        client: Client,
        salary_employee: Employee,
        company: Company,
        roles: None,
        worktype: WorkType,
        vehicle: Vehicle,
    ) -> None:
        """Контекст містить рядки звіту.

        Створюємо окремого механіка з labor_percent, щоб не заважати
        salary_employee-фікстурі.
        """
        mech_user: User = User.objects.create_user(
            username='salary_mech', password='test123',
        )
        mech: Employee = Employee.objects.create(
            user=mech_user, company=company,
            labor_percent=Decimal('10.00'),
        )
        mech.roles.set([Role.objects.get(codename='mechanic')])
        wo: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mech, vehicle=vehicle,
        )
        WorkOrderService.objects.create(
            work_order=wo, work_type=worktype,
            employee=mech,
            unit_price=Decimal('400.00'), quantity=2,
        )
        client.force_login(salary_employee.user)
        resp = client.get(self.url)
        assert resp.status_code == 200
        ctx = resp.context
        assert 'rows' in ctx
        assert len(ctx['rows']) >= 1
        assert ctx['total_earnings'] == Decimal('80.00')  # 800 * 10%
        assert ctx['total_services'] >= 1

    def test_filter_by_date(
        self,
        client: Client,
        salary_employee: Employee,
        company: Company,
        roles: None,
        worktype: WorkType,
        vehicle: Vehicle,
    ) -> None:
        """Фільтр за датою через view."""
        mech_user: User = User.objects.create_user(
            username='filter_mech', password='test123',
        )
        mech: Employee = Employee.objects.create(
            user=mech_user, company=company,
            labor_percent=Decimal('10.00'),
        )
        mech.roles.set([Role.objects.get(codename='mechanic')])
        wo: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mech, vehicle=vehicle,
        )
        WorkOrderService.objects.create(
            work_order=wo, work_type=worktype,
            employee=mech,
            unit_price=Decimal('300.00'), quantity=1,
        )
        client.force_login(salary_employee.user)
        # Фільтр датою з майбутнього — механік все одно показується, але з нулями
        resp = client.get(self.url, {'date_from': '2099-01-01'})
        assert resp.status_code == 200
        assert len(resp.context['rows']) == 1
        assert resp.context['rows'][0].services_count == 0
