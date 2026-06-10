"""Фікстури для тестування додатку worktypes."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth.models import User

from accounts.models import Employee, Role
from company.models import Company
from worktypes.models import WorkType


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
def worktype(db: Any, company: Company) -> WorkType:
    """Створює тестовий вид роботи."""
    return WorkType.objects.create(
        name='Заміна масла',
        description='Заміна моторної оливи та фільтра',
        category=WorkType.Category.MAINTENANCE,
        company=company,
    )
