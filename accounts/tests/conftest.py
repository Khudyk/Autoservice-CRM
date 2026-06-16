"""Фікстури для тестування додатку accounts."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth.models import User

from accounts.models import Employee, Role
from company.models import Company


@pytest.fixture(scope='module')
def company(django_db_blocker: Any) -> Company:
    """Створює тестову компанію (module-scoped)."""
    with django_db_blocker.unblock():
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
    """Створює тестового співробітника з роллю 'mechanic'."""
    emp = Employee.objects.create(
        user=user,
        company=company,
        phone='+380501112233',
    )
    role_mechanic = Role.objects.get(codename='mechanic')
    emp.roles.set([role_mechanic])
    return emp


@pytest.fixture
def another_user(db: Any) -> User:
    """Створює ще одного тестового користувача."""
    return User.objects.create_user(
        username='otheruser',
        email='other@user.com',
        password='otherpass123',
    )
