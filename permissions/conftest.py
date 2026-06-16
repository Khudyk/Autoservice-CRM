"""Фікстури для тестування додатку permissions."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth.models import User

from accounts.models import Employee, Role
from company.models import Company
from permissions.models import EmployeePermission, Module


# ============================================================
# Базові фікстури (компанія, користувач, співробітник)
# ============================================================


@pytest.fixture(scope='module')
def company(django_db_blocker: Any) -> Company:
    """Тестова компанія (module-scoped)."""
    with django_db_blocker.unblock():
        return Company.objects.create(
            name='Тестова компанія',
            email='test@company.com',
            phone='+380501234567',
        )


@pytest.fixture(scope='module')
def other_company(django_db_blocker: Any) -> Company:
    """Інша тестова компанія (module-scoped)."""
    with django_db_blocker.unblock():
        return Company.objects.create(
            name='Інша компанія',
            email='other@company.com',
            phone='+380509876543',
        )


@pytest.fixture
def user(db: Any) -> User:
    """Тестовий користувач."""
    return User.objects.create_user(
        username='testuser',
        email='test@user.com',
        password='testpass123',
        first_name='Тест',
        last_name='Користувач',
    )


@pytest.fixture
def another_user(db: Any) -> User:
    """Інший тестовий користувач."""
    return User.objects.create_user(
        username='otheruser',
        email='other@user.com',
        password='otherpass123',
    )


@pytest.fixture
def employee(
    db: Any,
    roles: None,
    user: User,
    company: Company,
) -> Employee:
    """Тестовий співробітник з роллю 'mechanic'."""
    emp = Employee.objects.create(
        user=user,
        company=company,
        phone='+380501112233',
    )
    role_mechanic = Role.objects.get(codename='mechanic')
    emp.roles.set([role_mechanic])
    return emp


@pytest.fixture
def other_employee(
    db: Any,
    roles: None,
    another_user: User,
    other_company: Company,
) -> Employee:
    """Співробітник іншої компанії."""
    emp = Employee.objects.create(
        user=another_user,
        company=other_company,
        phone='+380509998877',
    )
    role_manager = Role.objects.get(codename='manager')
    emp.roles.set([role_manager])
    return emp


# ============================================================
# Фікстури модулів
# ============================================================


@pytest.fixture
def module_parts(db: Any) -> Module:
    """Модуль 'parts'."""
    return Module.objects.get_or_create(
        codename='parts',
        defaults={'name': 'Запчастини'},
    )[0]


@pytest.fixture
def module_administration(db: Any) -> Module:
    """Модуль 'administration'."""
    return Module.objects.get_or_create(
        codename='administration',
        defaults={'name': 'Адміністрування'},
    )[0]


@pytest.fixture
def module_permissions_manage(db: Any) -> Module:
    """Модуль 'permissions_manage'."""
    return Module.objects.get_or_create(
        codename='permissions_manage',
        defaults={'name': 'Керування правами'},
    )[0]


# ============================================================
# Фікстури прав співробітників
# ============================================================


@pytest.fixture
def perm_read_parts(
    db: Any,
    employee: Employee,
    module_parts: Module,
) -> EmployeePermission:
    """Право на читання запчастин."""
    return EmployeePermission.objects.create(
        employee=employee,
        module=module_parts,
        can_read=True,
    )


@pytest.fixture
def perm_full_permissions_manage(
    db: Any,
    employee: Employee,
    module_permissions_manage: Module,
) -> EmployeePermission:
    """Повні права на керування правами."""
    return EmployeePermission.objects.create(
        employee=employee,
        module=module_permissions_manage,
        can_read=True,
        can_create=True,
        can_edit=True,
        can_delete=True,
    )
