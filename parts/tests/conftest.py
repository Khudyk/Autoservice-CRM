"""Фікстури для тестування додатку parts."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth.models import User

from accounts.models import Employee, Role
from company.models import Company
from parts.models import Part
from suppliers.models import Supplier


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
    """Створює тестового користувача."""
    return User.objects.create_user(
        username='testuser',
        email='test@user.com',
        password='testpass123',
        first_name='Тест',
        last_name='Користувач',
    )


@pytest.fixture
def employee(db: Any, roles: None, user: User, company: Company) -> Employee:
    """Створює тестового співробітника з роллю 'Майстер'."""
    emp = Employee.objects.create(
        user=user,
        company=company,
        phone='+380501112233',
    )
    emp.roles.set([Role.objects.get(codename='mechanic')])
    return emp


@pytest.fixture
def admin_user(db: Any) -> User:
    """Створює тестового користувача з роллю 'Адміністратор'."""
    user: User = User.objects.create_user(
        username='adminuser',
        email='admin@test.com',
        password='testpass123',
        first_name='Admin',
        last_name='User',
    )
    return user


@pytest.fixture
def admin_employee(db: Any, roles: None, admin_user: User, company: Company) -> Employee:
    """Створює тестового співробітника з роллю 'Адміністратор'."""
    emp = Employee.objects.create(
        user=admin_user,
        company=company,
        phone='+380509990000',
    )
    emp.roles.set([Role.objects.get(codename='admin')])
    return emp


@pytest.fixture
def other_company(db: Any) -> Company:
    """Інша компанія для тестів ізоляції."""
    return Company.objects.create(name='Інша компанія')


@pytest.fixture
def supplier(db: Any, company: Company) -> Supplier:
    """Створює тестового постачальника в тій самій компанії."""
    return Supplier.objects.create(
        name='ТОВ Автозапчастини',
        contact_person='Іван Петрович',
        phone='+380501234567',
        company=company,
    )


@pytest.fixture
def part(db: Any, company: Company) -> Part:
    """Створює тестову запчастину."""
    return Part.objects.create(
        name='Масляний фільтр',
        part_number='OC 260',
        manufacturer='MANN-FILTER',
        unit=Part.Unit.PIECE,
        selling_price=Decimal('250.00'),
        min_quantity=Decimal('2.00'),
        location='Стелаж A-1',
        company=company,
    )
