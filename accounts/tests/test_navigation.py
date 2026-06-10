"""Тести контекст-процесора навігації та Role-Based Menu."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.test import Client

from accounts.models import Employee, Role
from company.models import Company


class TestNavigationForAnonymousUser:
    """Навігація для анонімного користувача."""

    def test_anonymous_sees_only_login_link(self, client: Client) -> None:
        """Анонім бачить тільки кнопку 'Увійти', меню приховане."""
        response = client.get('/')
        content: str = response.content.decode()

        # Анонім бачить "Увійти"
        assert 'Увійти' in content
        # Не бачить пункти меню
        assert 'Компанії' not in content
        assert 'Співробітники' not in content
        assert 'Адмін' not in content


class TestNavigationForRegularUser:
    """Навігація для звичайного аутентифікованого користувача."""

    @pytest.fixture
    def logged_client(self, client: Client, db: None) -> Client:
        """Створює клієнта із залогіненим звичайним користувачем."""
        User.objects.create_user(
            username='regular',
            password='pass123',
        )
        client.login(username='regular', password='pass123')
        return client

    def test_regular_user_sees_main_menu(self, logged_client: Client) -> None:
        """Звичайний користувач (без Employee) бачить тільки загальнодоступні пункти."""
        response = logged_client.get('/')
        content: str = response.content.decode()
        assert 'Компанії' not in content     # тільки для admin-ролі
        assert 'Співробітники' not in content  # тільки для admin-ролі
        assert 'Автомобілі' in content
        assert 'Запчастини' in content
        assert 'Наряди' in content

    def test_regular_user_does_not_see_admin_menu(
        self,
        logged_client: Client,
    ) -> None:
        """Звичайний користувач НЕ бачить адмін-меню."""
        response = logged_client.get('/')
        content: str = response.content.decode()
        assert 'Адмін' not in content
        assert 'Адміністрування' not in content


class TestNavigationForStaffUser:
    """Навігація для користувача з is_staff=True."""

    @pytest.fixture
    def staff_client(self, client: Client, db: None) -> Client:
        """Створює клієнта із залогіненим staff-користувачем."""
        User.objects.create_user(
            username='staff_user',
            password='pass123',
            is_staff=True,
        )
        client.login(username='staff_user', password='pass123')
        return client

    def test_staff_user_sees_main_menu(self, staff_client: Client) -> None:
        """Staff користувач бачить усі пункти меню, включаючи 'Компанії'."""
        response = staff_client.get('/')
        content: str = response.content.decode()
        assert 'Компанії' in content  # staff = admin_role
        assert 'Співробітники' in content

    def test_staff_user_sees_admin_menu(self, staff_client: Client) -> None:
        """Staff користувач бачить адмін-меню (Адміністрування)."""
        response = staff_client.get('/')
        content: str = response.content.decode()
        assert 'Адмін' in content
        assert 'Адміністрування' in content


class TestNavigationForEmployeeAdminRole:
    """Навігація для користувача з бізнес-роллю admin/director."""

    @pytest.fixture
    def admin_role_client(self, client: Client, roles: None) -> Client:
        """Створює клієнта з Employee.role='admin', без is_staff."""
        user: User = User.objects.create_user(
            username='admin_role',
            password='pass123',
            is_staff=False,
        )
        company: Company = Company.objects.create(name='Admin Company')
        emp = Employee.objects.create(
            user=user,
            company=company,
        )
        emp.roles.set([Role.objects.get(codename='admin')])
        client.login(username='admin_role', password='pass123')
        return client

    @pytest.fixture
    def director_role_client(self, client: Client, roles: None) -> Client:
        """Створює клієнта з Employee.role='director', без is_staff."""
        user: User = User.objects.create_user(
            username='director_role',
            password='pass123',
            is_staff=False,
        )
        company: Company = Company.objects.create(name='Director Company')
        emp = Employee.objects.create(
            user=user,
            company=company,
        )
        emp.roles.set([Role.objects.get(codename='director')])
        client.login(username='director_role', password='pass123')
        return client

    def test_admin_role_sees_admin_menu(
        self,
        admin_role_client: Client,
    ) -> None:
        """Користувач з роллю 'admin' бачить адмін-меню, але не 'Компанії'."""
        response = admin_role_client.get('/')
        content: str = response.content.decode()
        assert 'Компанії' not in content  # тільки Django staff
        assert 'Адмін' in content
        assert 'Адміністрування' in content

    def test_director_role_sees_admin_menu(
        self,
        director_role_client: Client,
    ) -> None:
        """Користувач з роллю 'director' бачить адмін-меню, але не 'Компанії'."""
        response = director_role_client.get('/')
        content: str = response.content.decode()
        assert 'Компанії' not in content  # тільки Django staff
        assert 'Адмін' in content
        assert 'Адміністрування' in content


class TestNavigationForMechanicRole:
    """Навігація для користувача з бізнес-роллю mechanic (не admin)."""

    @pytest.fixture
    def mechanic_client(self, client: Client, roles: None) -> Client:
        """Створює клієнта з Employee.role='mechanic', без is_staff."""
        user: User = User.objects.create_user(
            username='mechanic_role',
            password='pass123',
        )
        company: Company = Company.objects.create(name='Service Co')
        emp = Employee.objects.create(
            user=user,
            company=company,
        )
        emp.roles.set([Role.objects.get(codename='mechanic')])
        client.login(username='mechanic_role', password='pass123')
        return client

    def test_mechanic_sees_main_but_not_admin_menu(
        self,
        mechanic_client: Client,
    ) -> None:
        """Майстер бачить основне меню, але не 'Компанії', 'Співробітники' та адмін."""
        response = mechanic_client.get('/')
        content: str = response.content.decode()
        assert 'Компанії' not in content       # тільки для admin-ролі
        assert 'Співробітники' not in content   # тільки для admin-ролі
        assert 'Автомобілі' in content
        assert 'Наряди' in content
        assert 'Адмін' not in content
