"""Тести контекст-процесора навігації."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from accounts.models import Employee, Role
from company.models import Company
from permissions.models import EmployeePermission, Module


MENU_ITEMS: set[str] = {
    'Клієнти',
    'Автомобілі',
    'Наряди',
    'Співробітники',
    'Довідники',
    'Закупівля / Розрахунки',
    'Адміністрування',
}

# Групи меню не показуються як текст у навігації, але їхні дочірні пункти — так
CHILD_ITEMS: set[str] = {
    'Види робіт',
    'Запчастини',
    'Постачальники',
    'Закупівля',
    'Розрахунки',
}

ALL_VISIBLE_ITEMS: set[str] = MENU_ITEMS | CHILD_ITEMS


def _create_employee_with_full_access(
    username: str, password: str = 'pass123', is_staff: bool = False,
) -> User:
    """Створює користувача з Employee та правами на всі модулі."""
    user = User.objects.create_user(
        username=username,
        password=password,
        is_staff=is_staff,
    )
    company = Company.objects.create(name='Test Company')
    role, _ = Role.objects.get_or_create(codename='admin', defaults={'name': 'Адміністратор'})
    employee = Employee.objects.create(user=user, company=company)
    employee.roles.add(role)

    # Створюємо права на всі модулі
    for module_data in [
        ('dashboard', 'Головна'),
        ('companies', 'Компанії'),
        ('clients', 'Клієнти'),
        ('vehicles', 'Автомобілі'),
        ('workorders', 'Наряди'),
        ('employees', 'Співробітники'),
        ('worktypes', 'Види робіт'),
        ('suppliers', 'Постачальники'),
        ('parts', 'Запчастини'),
        ('purchases', 'Закупівля'),
        ('payments', 'Розрахунки'),
        ('administration', 'Адміністрування'),
        ('permissions_manage', 'Керування правами'),
    ]:
        module, _ = Module.objects.get_or_create(
            codename=module_data[0],
            defaults={'name': module_data[1]},
        )
        EmployeePermission.objects.create(
            employee=employee, module=module, can_read=True,
        )
    return user


class TestNavigationForAnonymousUser:
    """Навігація для анонімного користувача."""

    def test_anonymous_redirected_to_login(self, client: Client, db: None) -> None:
        """Анонім перенаправляється на сторінку входу."""
        response = client.get('/')
        # Анонім отримує редирект на логін (302)
        assert response.status_code == 302
        assert response.url == reverse('login')


class TestNavigationForAnyUser:
    """Усі аутентифіковані користувачі бачать однакову навігацію."""

    @pytest.fixture(params=['regular', 'staff', 'admin_role', 'mechanic_role'])
    def logged_client(self, request, client: Client, db: None) -> Client:
        """Створює клієнта з різними типами користувачів."""
        is_staff = request.param == 'staff'
        user = _create_employee_with_full_access(
            username=request.param,
            password='pass123',
            is_staff=is_staff,
        )
        client.login(username=request.param, password='pass123')
        return client

    def test_user_sees_all_menu_items(self, logged_client: Client) -> None:
        """Аутентифікований користувач бачить усі пункти меню."""
        response = logged_client.get('/')
        content: str = response.content.decode()

        for item in ALL_VISIBLE_ITEMS:
            assert item in content, f'Пункт меню "{item}" має бути видимий'
