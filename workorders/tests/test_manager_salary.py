"""Тести для зведеного звіту по зарплаті менеджерів."""
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
from workorders.models import WorkOrder, WorkOrderPart, WorkOrderService
from workorders.services import (
    ManagerSummaryRow,
    get_all_managers_summary,
)
from worktypes.models import WorkType


# ──────────────────────────────────────────────
# Тести сервісу
# ──────────────────────────────────────────────


class TestGetAllManagersSummary:
    """Тести функції get_all_managers_summary."""

    def test_no_managers_returns_empty(
        self, db: None, company: Company,
    ) -> None:
        """Якщо немає співробітників з роллю manager — порожній список."""
        rows = get_all_managers_summary(company=company)
        assert rows == []

    def test_without_manager_role_not_in_report(
        self, db: None, company: Company, user: User, roles: None,
    ) -> None:
        """Співробітник без ролі manager не потрапляє у звіт."""
        emp: Employee = Employee.objects.create(
            user=user, company=company,
            labor_percent=Decimal('10.00'),
            parts_sale_percent=Decimal('5.00'),
        )
        emp.roles.set([Role.objects.get(codename='mechanic')])
        rows = get_all_managers_summary(company=company)
        assert rows == []

    def test_manager_no_orders(
        self, db: None, company: Company, user: User, roles: None,
    ) -> None:
        """Менеджер без нарядів — рядок з нульовими показниками."""
        mgr: Employee = Employee.objects.create(
            user=user, company=company,
            labor_percent=Decimal('10.00'),
            parts_sale_percent=Decimal('5.00'),
        )
        mgr.roles.set([Role.objects.get(codename='manager')])
        rows = get_all_managers_summary(company=company)
        assert len(rows) == 1
        row = rows[0]
        assert row.employee.pk == mgr.pk
        assert row.labor_percent == Decimal('10.00')
        assert row.parts_sale_percent == Decimal('5.00')
        assert row.orders_count == 0
        assert row.total_service_cost == Decimal('0.00')
        assert row.total_parts_profit == Decimal('0.00')
        assert row.total_earnings == Decimal('0.00')

    def test_manager_with_orders(
        self,
        db: None,
        company: Company,
        user: User,
        roles: None,
        worktype: WorkType,
        vehicle: Vehicle,
    ) -> None:
        """Менеджер з одним нарядом."""
        mgr: Employee = Employee.objects.create(
            user=user, company=company,
            labor_percent=Decimal('10.00'),
            parts_sale_percent=Decimal('5.00'),
        )
        mgr.roles.set([Role.objects.get(codename='manager')])

        wo: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mgr, vehicle=vehicle,
        )
        WorkOrderService.objects.create(
            work_order=wo, work_type=worktype,
            employee=mgr,
            unit_price=Decimal('1000.00'), quantity=2,
        )
        # Створюємо Part через ORM без part_lot для спрощення
        from parts.models import Part
        part: Part = Part.objects.create(
            name='Тестова деталь',
            part_number='TST-001',
            selling_price=Decimal('500.00'),
            quantity_on_hand=Decimal('100.00'),
            company=company,
        )
        WorkOrderPart.objects.create(
            work_order=wo, part=part,
            quantity=Decimal('3.00'),
            unit_price=Decimal('500.00'),
            purchase_price=Decimal('300.00'),
        )

        rows = get_all_managers_summary(company=company)
        assert len(rows) == 1
        row = rows[0]
        assert row.orders_count == 1
        # 1000 * 2 = 2000
        assert row.total_service_cost == Decimal('2000.00')
        # (500 - 300) * 3 = 600
        assert row.total_parts_profit == Decimal('600.00')
        # 2000 * 10 / 100 = 200
        assert row.service_earnings == Decimal('200.00')
        # 600 * 5 / 100 = 30
        assert row.parts_earnings == Decimal('30.00')
        # 200 + 30 = 230
        assert row.total_earnings == Decimal('230.00')

    def test_multiple_managers(
        self,
        db: None,
        company: Company,
        user: User,
        roles: None,
        worktype: WorkType,
        vehicle: Vehicle,
    ) -> None:
        """Два менеджери з різними відсотками."""
        mgr1: Employee = Employee.objects.create(
            user=user, company=company,
            labor_percent=Decimal('10.00'),
            parts_sale_percent=Decimal('5.00'),
        )
        mgr1.roles.set([Role.objects.get(codename='manager')])

        user2: User = User.objects.create_user(
            username='mgr2_user', password='test123',
        )
        mgr2: Employee = Employee.objects.create(
            user=user2, company=company,
            labor_percent=Decimal('15.00'),
            parts_sale_percent=Decimal('3.00'),
        )
        mgr2.roles.set([Role.objects.get(codename='manager')])

        wo1: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mgr1, vehicle=vehicle,
        )
        WorkOrderService.objects.create(
            work_order=wo1, work_type=worktype,
            employee=mgr1,
            unit_price=Decimal('1000.00'), quantity=1,
        )

        wo2: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mgr2, vehicle=vehicle,
        )
        WorkOrderService.objects.create(
            work_order=wo2, work_type=worktype,
            employee=mgr2,
            unit_price=Decimal('2000.00'), quantity=1,
        )

        rows = get_all_managers_summary(company=company)
        assert len(rows) == 2

        m1 = next(r for r in rows if r.employee.pk == mgr1.pk)
        assert m1.total_service_cost == Decimal('1000.00')
        assert m1.service_earnings == Decimal('100.00')  # 1000 * 10%

        m2 = next(r for r in rows if r.employee.pk == mgr2.pk)
        assert m2.total_service_cost == Decimal('2000.00')
        assert m2.service_earnings == Decimal('300.00')  # 2000 * 15%

        # Сортовано за earnings спаданням: mgr2 перший
        assert rows[0].employee.pk == mgr2.pk

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
        mgr: Employee = Employee.objects.create(
            user=user, company=company,
            labor_percent=Decimal('10.00'),
            parts_sale_percent=Decimal('5.00'),
        )
        mgr.roles.set([Role.objects.get(codename='manager')])

        # Старий наряд
        old_wo: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mgr, vehicle=vehicle,
        )
        WorkOrder.objects.filter(pk=old_wo.pk).update(
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        WorkOrderService.objects.create(
            work_order=old_wo, work_type=worktype,
            employee=mgr,
            unit_price=Decimal('500.00'), quantity=1,
        )

        # Новий наряд
        new_wo: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mgr, vehicle=vehicle,
        )
        WorkOrderService.objects.create(
            work_order=new_wo, work_type=worktype,
            employee=mgr,
            unit_price=Decimal('1000.00'), quantity=1,
        )

        rows = get_all_managers_summary(
            company=company,
            date_from=date(2024, 1, 1),
            date_to=date(2024, 12, 31),
        )
        assert len(rows) == 1
        assert rows[0].orders_count == 1
        assert rows[0].total_service_cost == Decimal('500.00')


# ──────────────────────────────────────────────
# Тести представлення
# ──────────────────────────────────────────────


class TestManagerSalaryView:
    """Тести представлення manager_salary_report."""

    url = reverse_lazy('manager_salary_report')

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

        Створюємо окремого менеджера, щоб не заважати salary_employee-фікстурі.
        """
        mgr_user: User = User.objects.create_user(
            username='salary_mgr', password='test123',
        )
        mgr: Employee = Employee.objects.create(
            user=mgr_user, company=company,
            labor_percent=Decimal('10.00'),
            parts_sale_percent=Decimal('5.00'),
        )
        mgr.roles.set([Role.objects.get(codename='manager')])

        wo: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mgr, vehicle=vehicle,
        )
        WorkOrderService.objects.create(
            work_order=wo, work_type=worktype,
            employee=mgr,
            unit_price=Decimal('1000.00'), quantity=1,
        )

        client.force_login(salary_employee.user)
        resp = client.get(self.url)
        assert resp.status_code == 200
        ctx = resp.context
        assert 'rows' in ctx
        assert len(ctx['rows']) >= 1
        assert ctx['total_earnings'] >= Decimal('0.00')
        assert ctx['total_orders'] >= 1

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
        mgr_user: User = User.objects.create_user(
            username='filter_mgr', password='test123',
        )
        mgr: Employee = Employee.objects.create(
            user=mgr_user, company=company,
            labor_percent=Decimal('10.00'),
            parts_sale_percent=Decimal('5.00'),
        )
        mgr.roles.set([Role.objects.get(codename='manager')])

        wo: WorkOrder = WorkOrder.objects.create(
            company=company, created_by=mgr, vehicle=vehicle,
        )
        WorkOrderService.objects.create(
            work_order=wo, work_type=worktype,
            employee=mgr,
            unit_price=Decimal('300.00'), quantity=1,
        )
        client.force_login(salary_employee.user)
        # Фільтр датою з майбутнього — всі менеджери показуються, але з нулями
        resp = client.get(self.url, {'date_from': '2099-01-01'})
        assert resp.status_code == 200
        # Є створений менеджер + salary_employee (директор не має manager-ролі — не в звіті)
        assert len(resp.context['rows']) == 1
        for row in resp.context['rows']:
            assert row.orders_count == 0
