"""Фікстури для тестування додатку vehicles."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.test import Client

from accounts.models import Employee, Role
from company.models import Company
from vehicles.models import Vehicle
from workorders.models import WorkOrder


@pytest.fixture
def company(db: Any) -> Company:
    """Створює тестову компанію."""
    return Company.objects.create(
        name='Тестова компанія',
        email='test@company.com',
        phone='+380501234567',
    )


@pytest.fixture
def user(db: Any) -> User:
    """Створює тестового користувача для ролі mechanic (без прав редагування каталогу)."""
    return User.objects.create_user(
        username='testuser',
        email='test@user.com',
        password='testpass123',
        first_name='Тест',
        last_name='Користувач',
    )


@pytest.fixture
def admin_user(db: Any) -> User:
    """Створює тестового користувача з роллю admin (має права редагування каталогу)."""
    return User.objects.create_user(
        username='admin_user',
        email='admin@user.com',
        password='testpass123',
        first_name='Admin',
        last_name='User',
    )


@pytest.fixture
def employee(db: Any, roles: None, user: User, company: Company) -> Employee:
    """Створює тестового співробітника з роллю Майстер (без прав редагування каталогу)."""
    emp = Employee.objects.create(
        user=user,
        company=company,
        phone='+380501112233',
    )
    emp.roles.set([Role.objects.get(codename='mechanic')])
    return emp


@pytest.fixture
def admin_employee(db: Any, roles: None, admin_user: User, company: Company) -> Employee:
    """Створює тестового співробітника з роллю Адміністратор (має права редагування каталогу)."""
    emp = Employee.objects.create(
        user=admin_user,
        company=company,
        phone='+380501112234',
    )
    emp.roles.set([Role.objects.get(codename='admin')])
    return emp


@pytest.fixture
def regular_client(client: Client, employee: Employee) -> Client:
    """Клієнт, залогінений як механік (без прав редагування каталогу)."""
    employee.user.is_staff = False
    employee.user.save()
    client.login(username=employee.user.username, password='testpass123')
    return client


@pytest.fixture
def admin_client(client: Client, admin_employee: Employee) -> Client:
    """Клієнт, залогінений як співробітник з роллю admin (має права редагування каталогу)."""
    admin_employee.user.is_staff = False
    admin_employee.user.save()
    client.login(username=admin_employee.user.username, password='testpass123')
    return client


@pytest.fixture
def mechanic_client(client: Client, employee: Employee) -> Client:
    """Клієнт, залогінений як механік (той самий що regular_client, але з явною назвою)."""
    employee.user.is_staff = False
    employee.user.save()
    client.login(username=employee.user.username, password='testpass123')
    return client


@pytest.fixture
def staff_client(client: Client, employee: Employee) -> Client:
    """Клієнт, залогінений як staff/superuser."""
    employee.user.is_staff = True
    employee.user.is_superuser = True
    employee.user.save()
    client.login(username=employee.user.username, password='testpass123')
    return client


@pytest.fixture
def other_company(db: Any) -> Company:
    """Інша компанія для тестів ізоляції."""
    return Company.objects.create(name='Інша компанія')


@pytest.fixture
def vehicle(db: Any, company: Company) -> Vehicle:
    """Створює тестовий автомобіль."""
    return Vehicle.objects.create(
        vin_code='WBA3A5C5XDF123456',
        brand='BMW',
        model='3 Series',
        year=2020,
        engine_type=Vehicle.EngineType.PETROL,
        engine_displacement=2.0,
        company=company,
    )


@pytest.fixture
def vehicle_with_work_order(
    db: Any, vehicle: Vehicle, company: Company, employee: Employee,
) -> Vehicle:
    """Створює автомобіль, на який є заказ-наряд."""
    WorkOrder.objects.create(
        company=company,
        vehicle=vehicle,
        created_by=employee,
    )
    return vehicle
