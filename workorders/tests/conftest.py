"""Фікстури для тестування додатку workorders (звіт про прибуток)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth.models import User

from accounts.models import Employee, Role
from company.models import Company
from parts.models import Part, PartLot
from vehicles.models import Vehicle
from workorders.models import WorkOrder, WorkOrderPart, WorkOrderService
from worktypes.models import WorkType


@pytest.fixture
def company(db: Any) -> Company:
    """Створює тестову компанію."""
    return Company.objects.create(
        name='Тестова СТО',
        email='sto@test.com',
        phone='+380501234567',
    )


@pytest.fixture
def user(db: Any) -> User:
    """Створює тестового користувача."""
    return User.objects.create_user(
        username='testuser',
        password='testpass123',
        first_name='Тест',
        last_name='Користувач',
    )


@pytest.fixture
def employee(db: Any, roles: None, user: User, company: Company) -> Employee:
    """Створює тестового співробітника (роль manager — для нарядів)."""
    emp = Employee.objects.create(
        user=user,
        company=company,
        phone='+380501112233',
    )
    emp.roles.set([Role.objects.get(codename='manager')])
    return emp


@pytest.fixture
def salary_employee(
    db: Any, roles: None, company: Company,
) -> Employee:
    """Створює співробітника з доступом до зарплатних звітів (роль director)."""
    user: User = User.objects.create_user(
        username='salary_user', password='test123',
        first_name='Зарплатний',
        last_name='Користувач',
    )
    emp = Employee.objects.create(
        user=user,
        company=company,
        phone='+380509998877',
    )
    emp.roles.set([Role.objects.get(codename='director')])
    return emp


@pytest.fixture
def vehicle(db: Any, company: Company) -> Vehicle:
    """Створює тестовий автомобіль."""
    return Vehicle.objects.create(
        vin_code='WDB12345678901234',
        brand='Toyota',
        model='Camry',
        year=2020,
        company=company,
    )


@pytest.fixture
def worktype(db: Any, company: Company) -> WorkType:
    """Створює тестовий вид роботи."""
    return WorkType.objects.create(
        name='Заміна масла',
        description='Заміна моторної оливи',
        category=WorkType.Category.MAINTENANCE,
        company=company,
    )


@pytest.fixture
def part(db: Any, company: Company) -> Part:
    """Створює тестову запчастину."""
    return Part.objects.create(
        name='Моторна олива 5W30',
        part_number='OIL-5W30',
        selling_price=Decimal('500.00'),
        quantity_on_hand=Decimal('100.00'),
        company=company,
    )


@pytest.fixture
def part_lot(db: Any, company: Company, part: Part) -> PartLot:
    """Створює тестову партію запчастин.

    У реальному проєкті PartLot створюється через PurchaseOrder,
    але для тесту створюємо напряму.
    """
    # Потрібен PurchaseOrderItem, але для тесту робимо спрощено
    from purchases.models import PurchaseOrder, PurchaseOrderItem
    from suppliers.models import Supplier

    supplier = Supplier.objects.create(
        name='Тестовий постачальник',
        company=company,
    )
    order = PurchaseOrder.objects.create(
        company=company,
        supplier=supplier,
        created_by=Employee.objects.create(
            user=User.objects.create_user(
                username='purchaser',
                password='pass123',
            ),
            company=company,
        ),
        status='received',
    )
    item = PurchaseOrderItem.objects.create(
        purchase_order=order,
        part=part,
        quantity_ordered=Decimal('100.00'),
        quantity_received=Decimal('100.00'),
        unit_price=Decimal('200.00'),
    )
    return PartLot.objects.create(
        purchase_item=item,
        part=part,
        quantity=Decimal('100.00'),
        purchase_price=Decimal('200.00'),
        company=company,
    )


@pytest.fixture
def work_order(
    db: Any,
    company: Company,
    vehicle: Vehicle,
    employee: Employee,
) -> WorkOrder:
    """Створює тестовий заказ-наряд."""
    return WorkOrder.objects.create(
        company=company,
        vehicle=vehicle,
        created_by=employee,
        status=WorkOrder.Status.COMPLETED,
    )


@pytest.fixture
def work_order_with_items(
    work_order: WorkOrder,
    worktype: WorkType,
    part: Part,
    part_lot: PartLot,
    employee: Employee,
) -> WorkOrder:
    """Створює заказ-наряд з роботами та запчастинами."""
    # Додаємо роботу
    WorkOrderService.objects.create(
        work_order=work_order,
        work_type=worktype,
        quantity=Decimal('2.00'),
        unit_price=Decimal('500.00'),
        employee=employee,
    )

    # Додаємо запчастину з партією та ціною закупівлі
    WorkOrderPart.objects.create(
        work_order=work_order,
        part=part,
        quantity=Decimal('3.00'),
        unit_price=Decimal('500.00'),  # продажна ціна
        part_lot=part_lot,
        purchase_price=part_lot.purchase_price,  # 200.00
    )

    return work_order
