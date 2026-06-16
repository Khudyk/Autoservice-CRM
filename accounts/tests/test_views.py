"""Тести представлень (views) додатку accounts."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from accounts.models import Employee, Role
from company.models import Company
from permissions.models import EmployeePermission, Module


# ----- Фікстури для авторизованих клієнтів -----


@pytest.fixture
def regular_client(client: Client, employee: Employee) -> Client:
    """Клієнт, залогінений як звичайний співробітник-механік (не staff)."""
    employee.user.is_staff = False
    employee.user.save()
    # Надаємо права на модуль employees (read, create, edit, delete)
    module, _ = Module.objects.get_or_create(
        codename='employees',
        defaults={'name': 'Співробітники'},
    )
    EmployeePermission.objects.update_or_create(
        employee=employee,
        module=module,
        defaults={'can_read': True, 'can_create': True, 'can_edit': True, 'can_delete': True},
    )
    client.login(username=employee.user.username, password='testpass123')
    return client


@pytest.fixture
def admin_client(client: Client, employee: Employee) -> Client:
    """Клієнт, залогінений як співробітник з роллю admin (не staff)."""
    employee.roles.set([Role.objects.get(codename='admin')])
    employee.user.is_staff = False
    employee.user.save()
    # Надаємо повні права на модуль employees
    module, _ = Module.objects.get_or_create(
        codename='employees',
        defaults={'name': 'Співробітники'},
    )
    EmployeePermission.objects.update_or_create(
        employee=employee,
        module=module,
        defaults={'can_read': True, 'can_create': True, 'can_edit': True, 'can_delete': True},
    )
    client.login(username=employee.user.username, password='testpass123')
    return client


@pytest.fixture
def staff_client(client: Client, employee: Employee) -> Client:
    """Клієнт, залогінений як staff."""
    employee.user.is_staff = True
    employee.user.is_superuser = True
    employee.user.save()
    client.login(username=employee.user.username, password='testpass123')
    return client


@pytest.fixture(scope='module')
def other_company(django_db_blocker: None) -> Company:
    """Інша компанія (не та, до якої прив'язаний employee) (module-scoped)."""
    with django_db_blocker.unblock():
        return Company.objects.create(name='Інша компанія')


@pytest.fixture
def other_user(db: None) -> User:
    """Користувач з іншої компанії."""
    return User.objects.create_user(
        username='other',
        password='pass123',
    )


@pytest.fixture
def other_employee(other_user: User, other_company: Company, roles: None) -> Employee:
    """Співробітник іншої компанії."""
    emp = Employee.objects.create(
        user=other_user,
        company=other_company,
    )
    emp.roles.set([Role.objects.get(codename='manager')])
    return emp


# ======================================================================
#  Employee LIST
# ======================================================================


class TestEmployeeListView:
    """Тести для employee_list view."""

    def test_any_user_can_access(
        self,
        regular_client: Client,
    ) -> None:
        """Будь-який аутентифікований користувач може переглядати список."""
        url: str = reverse('employee_list')
        response = regular_client.get(url)
        assert response.status_code == 200

    def test_sees_own_company_employees(
        self,
        regular_client: Client,
        employee: Employee,
        other_employee: Employee,
    ) -> None:
        """Користувач бачить тільки співробітників своєї компанії (multi-tenant)."""
        url: str = reverse('employee_list')
        response = regular_client.get(url)
        employees: list = response.context['page_obj']
        assert employee in employees  # своя компанія
        assert other_employee not in employees  # інша компанія — не видно


# ======================================================================
#  Employee CREATE
# ======================================================================


class TestEmployeeCreateView:
    """Тести для employee_create view."""

    CREATE_DATA: dict = {
        'username': 'new_user',
        'email': 'new@user.local',
        'first_name': 'Новий',
        'last_name': 'Користувач',
        'password': 'testpass123',
        'phone': '+380501234567',
        'is_active': True,
        'company': '',
    }

    def _get_create_data(self, roles_pks: list[int], **overrides) -> dict:
        """Повертає CREATE_DATA з ролями та перевизначеннями."""
        data = {**self.CREATE_DATA, 'roles': roles_pks}
        data.update(overrides)
        return data

    def test_any_user_can_access(
        self, regular_client: Client,
    ) -> None:
        """Будь-який аутентифікований користувач може створювати співробітників."""
        url: str = reverse('employee_create')
        response = regular_client.get(url)
        assert response.status_code == 200

    def test_create_creates_user_and_employee(
        self,
        admin_client: Client,
        employee: Employee,
    ) -> None:
        """Створення User + Employee."""
        role_mechanic = Role.objects.get(codename='mechanic')
        url: str = reverse('employee_create')
        data = self._get_create_data(
            roles_pks=[role_mechanic.pk],
            company=employee.company_id,
        )
        response = admin_client.post(url, data, follow=True)
        assert response.status_code == 200

        # Перевіряємо, що створився User
        new_user = User.objects.get(username='new_user')
        assert new_user.email == 'new@user.local'
        assert new_user.check_password('testpass123')

        # Перевіряємо, що створився Employee
        created = Employee.objects.get(user=new_user)
        assert created.has_role('mechanic')

    def test_duplicate_username_shows_error(
        self,
        admin_client: Client,
        employee: Employee,
    ) -> None:
        """При спробі створити з існуючим username — помилка валідації."""
        role_mechanic = Role.objects.get(codename='mechanic')
        url: str = reverse('employee_create')
        data = self._get_create_data(
            roles_pks=[role_mechanic.pk],
            username=employee.user.username,
        )
        response = admin_client.post(url, data)
        assert response.status_code == 200
        assert response.context['form'].errors

    def test_get_form_returns_200(
        self,
        admin_client: Client,
    ) -> None:
        """Отримання форми створення (GET)."""
        url: str = reverse('employee_create')
        response = admin_client.get(url)
        assert response.status_code == 200
        assert 'form' in response.context
        assert 'title' in response.context
        assert response.context['title'] == 'Новий співробітник'

    def test_post_with_multiple_roles(
        self,
        admin_client: Client,
        employee: Employee,
    ) -> None:
        """Створення співробітника з декількома ролями."""
        role_admin = Role.objects.get(codename='admin')
        role_purchaser = Role.objects.get(codename='purchaser')
        url: str = reverse('employee_create')
        data = self._get_create_data(
            roles_pks=[role_admin.pk, role_purchaser.pk],
            username='multi_role_user',
            company=employee.company_id,
        )
        response = admin_client.post(url, data, follow=True)
        assert response.status_code == 200

        created = Employee.objects.get(user__username='multi_role_user')
        assert created.roles.count() == 2
        assert created.has_role('admin')
        assert created.has_role('purchaser')

    def test_post_missing_company_shows_errors(
        self,
        admin_client: Client,
    ) -> None:
        """POST без company — форма повертає помилку."""
        url: str = reverse('employee_create')
        data = {
            'username': 'no_company_user',
            'email': 'no@user.com',
            'first_name': 'Без',
            'last_name': 'Компанії',
        }
        response = admin_client.post(url, data)
        assert response.status_code == 200
        assert response.context['form'].errors
        assert 'company' in response.context['form'].errors


# ======================================================================
#  Employee UPDATE
# ======================================================================


class TestEmployeeUpdateView:
    """Тести для employee_update view."""

    def _get_update_data(self, roles_pks: list[int], company_pk: int | None = None, **overrides) -> dict:
        """Повертає дані для оновлення з ролями та перевизначеннями."""
        data: dict = {
            'email': 'updated@email.local',
            'first_name': 'Оновлений',
            'last_name': 'Тест',
            'roles': roles_pks,
            'phone': '+380509990000',
            'is_active': False,
        }
        if company_pk is not None:
            data['company'] = company_pk
        data.update(overrides)
        return data

    def test_any_user_can_access(
        self,
        regular_client: Client,
        employee: Employee,
    ) -> None:
        """Будь-який аутентифікований користувач може редагувати співробітника."""
        url: str = reverse('employee_update', kwargs={'pk': employee.pk})
        response = regular_client.get(url)
        assert response.status_code == 200

    def test_update_employee_success(
        self,
        regular_client: Client,
        employee: Employee,
    ) -> None:
        """Успішне оновлення співробітника та його користувача."""
        role_director = Role.objects.get(codename='director')
        url: str = reverse('employee_update', kwargs={'pk': employee.pk})
        regular_client.post(url, self._get_update_data(
            roles_pks=[role_director.pk],
            company_pk=employee.company_id,
        ))
        employee.refresh_from_db()
        employee.user.refresh_from_db()
        assert employee.has_role('director')
        assert employee.phone == '+380509990000'
        assert employee.is_active is False
        assert employee.user.email == 'updated@email.local'
        assert employee.user.first_name == 'Оновлений'

    def test_update_employee_password(
        self,
        regular_client: Client,
        employee: Employee,
    ) -> None:
        """Оновлення пароля користувача."""
        role_mechanic = Role.objects.get(codename='mechanic')
        url: str = reverse('employee_update', kwargs={'pk': employee.pk})
        regular_client.post(url, {
            'password': 'newpass321',
            'roles': [role_mechanic.pk],
            'company': employee.company_id,
        })
        employee.user.refresh_from_db()
        assert employee.user.check_password('newpass321')


# ======================================================================
#  Employee DELETE
# ======================================================================


class TestEmployeeDeleteView:
    """Тести для employee_delete view."""

    def test_any_user_can_delete(
        self,
        regular_client: Client,
        company: Company,
    ) -> None:
        """Будь-який аутентифікований користувач може видалити співробітника."""
        # Створюємо окремого співробітника для видалення
        target_user = User.objects.create_user(
            username='target_for_delete',
            password='pass123',
        )
        target_employee = Employee.objects.create(
            user=target_user,
            company=company,
        )
        target_employee.roles.set([Role.objects.get(codename='mechanic')])
        url: str = reverse('employee_delete', kwargs={'pk': target_employee.pk})
        response = regular_client.post(url, follow=True)
        assert not Employee.objects.filter(pk=target_employee.pk).exists()
        assert response.status_code == 200
