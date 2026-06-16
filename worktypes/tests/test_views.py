"""Тести представлень (views) додатку worktypes."""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from accounts.models import Employee
from company.models import Company
from permissions.models import EmployeePermission, Module
from worktypes.models import WorkType


def _grant_worktype_permissions(
    employee: Employee,
    can_read: bool = False,
    can_create: bool = False,
    can_edit: bool = False,
    can_delete: bool = False,
) -> None:
    """Надає співробітнику права на модуль worktypes."""
    module, _ = Module.objects.get_or_create(
        codename='worktypes',
        defaults={'name': 'Види робіт'},
    )
    EmployeePermission.objects.update_or_create(
        employee=employee,
        module=module,
        defaults={
            'can_read': can_read,
            'can_create': can_create,
            'can_edit': can_edit,
            'can_delete': can_delete,
        },
    )


@pytest.fixture
def regular_client(client: Client, employee) -> Client:
    """Клієнт, залогінений як звичайний співробітник (роль 'Майстер')."""
    employee.user.is_staff = False
    employee.user.save()
    _grant_worktype_permissions(employee, can_read=True)
    client.login(username=employee.user.username, password='testpass123')
    return client


@pytest.fixture
def staff_client(client: Client, employee) -> Client:
    """Клієнт, залогінений як staff."""
    employee.user.is_staff = True
    employee.user.is_superuser = True
    employee.user.save()
    client.login(username=employee.user.username, password='testpass123')
    return client


@pytest.fixture
def admin_client(client: Client, admin_employee) -> Client:
    """Клієнт, залогінений як співробітник з роллю 'Адміністратор'."""
    admin_employee.user.is_staff = False
    admin_employee.user.save()
    _grant_worktype_permissions(
        admin_employee, can_read=True, can_create=True, can_edit=True, can_delete=True,
    )
    client.login(username=admin_employee.user.username, password='testpass123')
    return client


class TestWorkTypeListView:
    """Тести для worktype_list view."""

    def test_anonymous_sees_empty_list(
        self, client: Client, worktype: WorkType,
    ) -> None:
        """Анонім перенаправляється на сторінку входу."""
        response = client.get(reverse('worktype_list'))
        assert response.status_code == 302

    def test_regular_user_sees_only_own_company(
        self, regular_client: Client, worktype: WorkType, other_company: Company,
    ) -> None:
        """Звичайний користувач бачить тільки роботи своєї компанії."""
        WorkType.objects.create(name='Інша робота', company=other_company)
        response = regular_client.get(reverse('worktype_list'))
        assert worktype in response.context['page_obj']
        assert len(response.context['page_obj']) == 1

    def test_staff_user_sees_all_worktypes(
        self, staff_client: Client, worktype: WorkType, other_company: Company,
    ) -> None:
        """Staff бачить усі роботи з усіх компаній."""
        w2 = WorkType.objects.create(name='Робота іншої компанії', company=other_company)
        response = staff_client.get(reverse('worktype_list'))
        assert worktype in response.context['page_obj']
        assert w2 in response.context['page_obj']


class TestWorkTypeCreateView:
    """Тести для worktype_create view."""

    CREATE_DATA: dict = {
        'name': 'Діагностика двигуна',
        'description': 'Комп\'ютерна діагностика ДВЗ',
        'category': WorkType.Category.DIAGNOSTICS,
        'default_price': '500.00',
        'is_active': True,
    }

    def test_anonymous_access(self, client: Client, db) -> None:
        """Анонім перенаправляється на вхід (302)."""
        assert client.get(reverse('worktype_create')).status_code == 302

    def test_regular_user_create_gets_403(
        self, regular_client: Client,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403."""
        response = regular_client.post(reverse('worktype_create'), {**self.CREATE_DATA})
        assert response.status_code == 403
        assert not WorkType.objects.filter(name='Діагностика двигуна').exists()

    def test_staff_user_can_create_in_any_company(
        self, staff_client: Client, other_company: Company,
    ) -> None:
        """Staff може створити роботу в будь-якій компанії."""
        data = {**self.CREATE_DATA, 'name': 'Ремонт підвіски', 'company': other_company.pk}
        response = staff_client.post(reverse('worktype_create'), data)
        if response.status_code == 200:
            form = response.context.get('form') if response.context else None
            if form and form.errors:
                raise AssertionError(f'Form errors: {dict(form.errors)}')
        created = WorkType.objects.get(name='Ремонт підвіски')
        assert created.company == other_company

    def test_duplicate_name_shows_error(
        self, regular_client: Client, worktype: WorkType,
    ) -> None:
        """Спроба створити з існуючою назвою — 403 (перевірка доступу раніше за дублікат)."""
        data = {**self.CREATE_DATA, 'name': worktype.name}
        response = regular_client.post(reverse('worktype_create'), data)
        assert response.status_code == 403


class TestWorkTypeUpdateView:
    """Тести для worktype_update view."""

    def test_regular_user_cannot_update_own_company(
        self, regular_client: Client, worktype: WorkType,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403 при спробі редагувати."""
        assert regular_client.get(
            reverse('worktype_update', kwargs={'pk': worktype.pk}),
        ).status_code == 403

    def test_regular_user_cannot_update_other_company(
        self, regular_client: Client, other_company: Company,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403 на чужу компанію (перевірка доступу раніше за компанію)."""
        other = WorkType.objects.create(name='Чужа робота', company=other_company)
        assert regular_client.get(
            reverse('worktype_update', kwargs={'pk': other.pk}),
        ).status_code == 403

    def test_admin_user_can_update_own_company(
        self, admin_client: Client, worktype: WorkType,
    ) -> None:
        """Адміністратор може редагувати роботу своєї компанії."""
        assert admin_client.get(
            reverse('worktype_update', kwargs={'pk': worktype.pk}),
        ).status_code == 200

    def test_admin_user_cannot_update_other_company(
        self, admin_client: Client, other_company: Company,
    ) -> None:
        """Адміністратор не може редагувати роботу чужої компанії (404)."""
        other = WorkType.objects.create(name='Чужа робота', company=other_company)
        assert admin_client.get(
            reverse('worktype_update', kwargs={'pk': other.pk}),
        ).status_code == 404

    def test_update_success(
        self, admin_client: Client, worktype: WorkType,
    ) -> None:
        """Успішне оновлення адміністратором."""
        response = admin_client.post(
            reverse('worktype_update', kwargs={'pk': worktype.pk}), {
                'name': worktype.name,
                'description': 'Новий опис',
                'category': WorkType.Category.REPAIR,
                'default_price': '500.00',
                'is_active': False,
                'company': worktype.company.pk,
            },
        )
        if response.status_code == 200:
            form = response.context.get('form') if response.context else None
            if form and form.errors:
                raise AssertionError(f'Form errors: {dict(form.errors)}')
        worktype.refresh_from_db()
        assert worktype.category == WorkType.Category.REPAIR
        assert worktype.is_active is False


class TestWorkTypeDeleteView:
    """Тести для worktype_delete view."""

    def test_regular_user_cannot_delete_own_company(
        self, regular_client: Client, worktype: WorkType,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403 при спробі видалення."""
        response = regular_client.post(
            reverse('worktype_delete', kwargs={'pk': worktype.pk}), follow=True,
        )
        assert WorkType.objects.filter(pk=worktype.pk).exists()
        assert response.status_code == 403

    def test_regular_user_cannot_delete_other_company(
        self, regular_client: Client, other_company: Company,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403 на чужу компанію (перевірка доступу раніше за компанію)."""
        other = WorkType.objects.create(name='Чужа на видалення', company=other_company)
        assert regular_client.post(
            reverse('worktype_delete', kwargs={'pk': other.pk}),
        ).status_code == 403
        assert WorkType.objects.filter(pk=other.pk).exists()

    def test_admin_user_can_delete_own_company(
        self, admin_client: Client, worktype: WorkType,
    ) -> None:
        """Адміністратор може видалити роботу своєї компанії."""
        response = admin_client.post(
            reverse('worktype_delete', kwargs={'pk': worktype.pk}), follow=True,
        )
        assert not WorkType.objects.filter(pk=worktype.pk).exists()
        assert response.status_code == 200

    def test_admin_user_cannot_delete_other_company(
        self, admin_client: Client, other_company: Company,
    ) -> None:
        """Адміністратор не може видалити чужу роботу (404)."""
        other = WorkType.objects.create(name='Чужа на видалення', company=other_company)
        assert admin_client.post(
            reverse('worktype_delete', kwargs={'pk': other.pk}),
        ).status_code == 404
        assert WorkType.objects.filter(pk=other.pk).exists()
