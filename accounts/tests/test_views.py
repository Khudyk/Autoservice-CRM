"""Тести представлень (views) додатку accounts."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from accounts.models import Employee, Role
from company.models import Company


# ----- Фікстури для авторизованих клієнтів -----


@pytest.fixture
def regular_client(client: Client, employee: Employee) -> Client:
    """Клієнт, залогінений як звичайний співробітник-механік (не staff)."""
    employee.user.is_staff = False
    employee.user.save()
    client.login(username=employee.user.username, password='testpass123')
    return client


@pytest.fixture
def admin_client(client: Client, employee: Employee) -> Client:
    """Клієнт, залогінений як співробітник з роллю admin (не staff)."""
    employee.roles.set([Role.objects.get(codename='admin')])
    employee.user.is_staff = False
    employee.user.save()
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


@pytest.fixture
def other_company(db: None) -> Company:
    """Інша компанія (не та, до якої прив'язаний employee)."""
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

    def test_anonymous_redirects_to_login(self, client: Client) -> None:
        """Анонім перенаправляється на сторінку входу."""
        url: str = reverse('employee_list')
        response = client.get(url)
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_regular_user_gets_403(
        self,
        regular_client: Client,
    ) -> None:
        """Механік отримує 403 — доступ лише керівникам."""
        url: str = reverse('employee_list')
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_admin_user_sees_only_own_company(
        self,
        admin_client: Client,
        employee: Employee,
        other_employee: Employee,
    ) -> None:
        """Адміністратор бачить тільки співробітників своєї компанії."""
        url: str = reverse('employee_list')
        response = admin_client.get(url)
        employees: list = response.context['page_obj']
        assert employee in employees
        assert other_employee not in employees

    def test_staff_user_sees_all_employees(
        self,
        staff_client: Client,
        employee: Employee,
        other_employee: Employee,
    ) -> None:
        """Staff бачить усіх співробітників з усіх компаній."""
        url: str = reverse('employee_list')
        response = staff_client.get(url)
        employees: list = response.context['page_obj']
        assert employee in employees
        assert other_employee in employees

    def test_admin_user_companies_contains_only_own(
        self,
        admin_client: Client,
        company: Company,
        other_company: Company,
    ) -> None:
        """Адміністратор у фільтрі бачить тільки свою компанію."""
        url: str = reverse('employee_list')
        response = admin_client.get(url)
        companies: list = response.context['companies']
        assert company in companies
        assert other_company not in companies

    def test_staff_user_can_filter_by_company(
        self,
        staff_client: Client,
        employee: Employee,
        other_employee: Employee,
        other_company: Company,
    ) -> None:
        """Staff може фільтрувати через ?company=<pk>."""
        url: str = reverse('employee_list')
        response = staff_client.get(url, {'company': other_company.pk})
        employees: list = response.context['page_obj']
        assert other_employee in employees
        assert employee not in employees


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
    }

    def _get_create_data(self, roles_pks: list[int], **overrides) -> dict:
        """Повертає CREATE_DATA з ролями та перевизначеннями."""
        data = {**self.CREATE_DATA, 'roles': roles_pks}
        data.update(overrides)
        return data

    def test_regular_user_gets_403(
        self, regular_client: Client,
    ) -> None:
        """Механік отримує 403 — створення лише для керівників."""
        url: str = reverse('employee_create')
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_admin_user_create_creates_user_and_employee(
        self,
        admin_client: Client,
        employee: Employee,
    ) -> None:
        """Адміністратор створює User + Employee у своїй компанії."""
        role_mechanic = Role.objects.get(codename='mechanic')
        url: str = reverse('employee_create')
        data = self._get_create_data(roles_pks=[role_mechanic.pk])
        response = admin_client.post(url, data, follow=True)
        assert response.status_code == 200

        # Перевіряємо, що створився User
        new_user = User.objects.get(username='new_user')
        assert new_user.email == 'new@user.local'
        assert new_user.check_password('testpass123')

        # Перевіряємо, що створився Employee у правильній компанії
        created = Employee.objects.get(user=new_user)
        assert created.company == employee.company
        assert created.has_role('mechanic')

    def test_staff_user_can_create_in_any_company(
        self,
        staff_client: Client,
        other_company: Company,
    ) -> None:
        """Staff може створити співробітника в будь-якій компанії."""
        role_director = Role.objects.get(codename='director')
        url: str = reverse('employee_create')
        data = self._get_create_data(
            roles_pks=[role_director.pk],
            username='staff_new_user',
            company=other_company.pk,
        )
        staff_client.post(url, data)
        new_user = User.objects.get(username='staff_new_user')
        created = Employee.objects.get(user=new_user)
        assert created.company == other_company
        assert created.has_role('director')

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
            username=employee.user.username,  # вже існує
        )
        response = admin_client.post(url, data)
        assert response.status_code == 200
        assert response.context['form'].errors

    def test_admin_get_form_returns_200(
        self,
        admin_client: Client,
    ) -> None:
        """Адміністратор отримує форму створення (GET)."""
        url: str = reverse('employee_create')
        response = admin_client.get(url)
        assert response.status_code == 200
        assert 'form' in response.context
        assert 'title' in response.context
        assert response.context['title'] == 'Новий співробітник'

    def test_staff_get_form_returns_200(
        self,
        staff_client: Client,
    ) -> None:
        """Staff отримує форму створення (GET)."""
        url: str = reverse('employee_create')
        response = staff_client.get(url)
        assert response.status_code == 200
        assert 'form' in response.context

    def test_admin_post_with_multiple_roles(
        self,
        admin_client: Client,
        employee: Employee,
    ) -> None:
        """Адміністратор створює співробітника з декількома ролями."""
        role_admin = Role.objects.get(codename='admin')
        role_purchaser = Role.objects.get(codename='purchaser')
        url: str = reverse('employee_create')
        data = self._get_create_data(
            roles_pks=[role_admin.pk, role_purchaser.pk],
            username='multi_role_user',
        )
        response = admin_client.post(url, data, follow=True)
        assert response.status_code == 200

        created = Employee.objects.get(user__username='multi_role_user')
        assert created.roles.count() == 2
        assert created.has_role('admin')
        assert created.has_role('purchaser')

    def test_admin_post_missing_username_shows_errors(
        self,
        admin_client: Client,
    ) -> None:
        """POST без username — форма повертає помилку."""
        url: str = reverse('employee_create')
        data = {
            'email': 'no@user.com',
            'first_name': 'Без',
            'last_name': 'Імені',
            'company': '',  # буде підставлено компанію адміна
        }
        response = admin_client.post(url, data)
        assert response.status_code == 200
        assert response.context['form'].errors
        # Має бути помилка хоча б по username або company
        assert (
            'username' in response.context['form'].errors
            or 'company' in response.context['form'].errors
        )

    def test_anonymous_post_redirects_to_login(
        self,
        client: Client,
    ) -> None:
        """Анонімний POST перенаправляється на сторінку входу."""
        url: str = reverse('employee_create')
        response = client.post(url, {'username': 'hacker'})
        assert response.status_code == 302
        assert '/login/' in response.url


# ======================================================================
#  Employee UPDATE
# ======================================================================


class TestEmployeeUpdateView:
    """Тести для employee_update view."""

    def _get_update_data(self, roles_pks: list[int], **overrides) -> dict:
        """Повертає дані для оновлення з ролями та перевизначеннями."""
        data: dict = {
            'email': 'updated@email.local',
            'first_name': 'Оновлений',
            'last_name': 'Тест',
            'roles': roles_pks,
            'phone': '+380509990000',
            'is_active': False,
        }
        data.update(overrides)
        return data

    def test_regular_user_gets_403(
        self,
        regular_client: Client,
        employee: Employee,
    ) -> None:
        """Механік отримує 403 — редагування лише для керівників."""
        url: str = reverse('employee_update', kwargs={'pk': employee.pk})
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_regular_user_cannot_access_other_company_employee(
        self,
        regular_client: Client,
        other_employee: Employee,
    ) -> None:
        """Механік отримує 403 на редагування чужого співробітника."""
        url: str = reverse('employee_update', kwargs={'pk': other_employee.pk})
        response = regular_client.get(url)
        assert response.status_code == 403

    def test_admin_user_can_update_own_company_employee(
        self,
        admin_client: Client,
        employee: Employee,
    ) -> None:
        """Адміністратор може редагувати співробітника своєї компанії."""
        url: str = reverse('employee_update', kwargs={'pk': employee.pk})
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_admin_user_cannot_update_other_company_employee(
        self,
        admin_client: Client,
        other_employee: Employee,
    ) -> None:
        """Адміністратор не може редагувати чужу компанію (404)."""
        url: str = reverse('employee_update', kwargs={'pk': other_employee.pk})
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_update_employee_success(
        self,
        admin_client: Client,
        employee: Employee,
    ) -> None:
        """Успішне оновлення співробітника та його користувача."""
        role_director = Role.objects.get(codename='director')
        url: str = reverse('employee_update', kwargs={'pk': employee.pk})
        admin_client.post(url, self._get_update_data(roles_pks=[role_director.pk]))
        employee.refresh_from_db()
        employee.user.refresh_from_db()
        assert employee.has_role('director')
        assert employee.phone == '+380509990000'
        assert employee.is_active is False
        assert employee.user.email == 'updated@email.local'
        assert employee.user.first_name == 'Оновлений'

    def test_update_employee_password(
        self,
        admin_client: Client,
        employee: Employee,
    ) -> None:
        """Оновлення пароля користувача."""
        role_mechanic = Role.objects.get(codename='mechanic')
        url: str = reverse('employee_update', kwargs={'pk': employee.pk})
        admin_client.post(url, {
            'password': 'newpass321',
            'roles': [role_mechanic.pk],
        })
        employee.user.refresh_from_db()
        assert employee.user.check_password('newpass321')


# ======================================================================
#  Employee DELETE
# ======================================================================


class TestEmployeeDeleteView:
    """Тести для employee_delete view."""

    def test_regular_user_gets_403(
        self,
        regular_client: Client,
        employee: Employee,
    ) -> None:
        """Механік отримує 403 — видалення лише для керівників."""
        url: str = reverse('employee_delete', kwargs={'pk': employee.pk})
        response = regular_client.post(url)
        assert response.status_code == 403
        assert Employee.objects.filter(pk=employee.pk).exists()

    def test_regular_user_cannot_access_other_company_employee(
        self,
        regular_client: Client,
        other_employee: Employee,
    ) -> None:
        """Механік отримує 403 на видалення чужого співробітника."""
        url: str = reverse('employee_delete', kwargs={'pk': other_employee.pk})
        response = regular_client.post(url)
        assert response.status_code == 403
        assert Employee.objects.filter(pk=other_employee.pk).exists()

    def test_admin_user_can_delete_own_company_employee(
        self,
        admin_client: Client,
        company: Company,
        employee: Employee,
    ) -> None:
        """Адміністратор може видалити співробітника своєї компанії (не себе)."""
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
        response = admin_client.post(url, follow=True)
        assert not Employee.objects.filter(pk=target_employee.pk).exists()
        assert response.status_code == 200

    def test_admin_user_cannot_delete_other_company_employee(
        self,
        admin_client: Client,
        other_employee: Employee,
    ) -> None:
        """Адміністратор не може видалити чужого співробітника (404)."""
        url: str = reverse('employee_delete', kwargs={'pk': other_employee.pk})
        response = admin_client.post(url)
        assert response.status_code == 404
        assert Employee.objects.filter(pk=other_employee.pk).exists()
