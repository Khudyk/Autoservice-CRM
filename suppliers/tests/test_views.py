"""Тести представлень (views) додатку suppliers."""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from company.models import Company
from suppliers.models import Supplier


@pytest.fixture
def regular_client(client: Client, employee) -> Client:
    """Клієнт, залогінений як звичайний співробітник (без is_staff)."""
    employee.user.is_staff = False
    employee.user.save()
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
    client.login(username=admin_employee.user.username, password='testpass123')
    return client


class TestSupplierListView:
    """Тести для supplier_list view."""

    def test_anonymous_sees_empty_list(self, client: Client, supplier: Supplier) -> None:
        """Анонім перенаправляється на сторінку входу."""
        response = client.get(reverse('supplier_list'))
        assert response.status_code == 302

    def test_regular_user_sees_only_own_company(
        self, regular_client: Client, supplier: Supplier, other_company: Company,
    ) -> None:
        """Звичайний користувач бачить тільки постачальників своєї компанії."""
        Supplier.objects.create(name='Інший постачальник', company=other_company)
        response = regular_client.get(reverse('supplier_list'))
        suppliers: list = response.context['page_obj']
        assert supplier in suppliers
        assert len(suppliers) == 1

    def test_staff_user_sees_all_suppliers(
        self, staff_client: Client, supplier: Supplier, other_company: Company,
    ) -> None:
        """Staff бачить усіх постачальників з усіх компаній."""
        s2: Supplier = Supplier.objects.create(
            name='Постачальник іншої компанії', company=other_company,
        )
        response = staff_client.get(reverse('supplier_list'))
        suppliers: list = response.context['page_obj']
        assert supplier in suppliers
        assert s2 in suppliers

    def test_staff_user_can_filter_by_company(
        self, staff_client: Client, supplier: Supplier, other_company: Company,
    ) -> None:
        """Staff може фільтрувати через ?company=<pk>."""
        s2: Supplier = Supplier.objects.create(
            name='Фільтрований постачальник', company=other_company,
        )
        response = staff_client.get(reverse('supplier_list'), {'company': other_company.pk})
        suppliers: list = response.context['page_obj']
        assert s2 in suppliers
        assert supplier not in suppliers


class TestSupplierCreateView:
    """Тести для supplier_create view."""

    CREATE_DATA: dict = {
        'name': 'ТОВ Нова постачка',
        'contact_person': 'Олег Степаненко',
        'phone': '+380509876543',
        'email': 'new@supplier.ua',
        'address': 'м. Львів, вул. Тестова, 10',
        'notes': 'Новий постачальник',
        'is_active': True,
    }

    def test_anonymous_get_redirects_to_login(self, client: Client, db) -> None:
        """GET /suppliers/create/ для аноніма — 302."""
        response = client.get(reverse('supplier_create'))
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_regular_user_create_gets_403(
        self, regular_client: Client,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403."""
        response = regular_client.post(reverse('supplier_create'), self.CREATE_DATA)
        assert response.status_code == 403
        assert not Supplier.objects.filter(name='ТОВ Нова постачка').exists()

    def test_staff_user_can_create_in_any_company(
        self, staff_client: Client, other_company: Company,
    ) -> None:
        """Staff може створити постачальника в будь-якій компанії."""
        data: dict = {**self.CREATE_DATA, 'name': 'Staff постачальник', 'company': other_company.pk}
        response = staff_client.post(reverse('supplier_create'), data)
        if response.status_code == 200 and response.context and response.context.get('form') and response.context['form'].errors:
            raise AssertionError(f'Form errors: {dict(response.context["form"].errors)}')

        created: Supplier = Supplier.objects.get(name='Staff постачальник')
        assert created.company == other_company

    def test_duplicate_name_shows_error(self, regular_client: Client, supplier: Supplier) -> None:
        """Спроба створити з існуючою назвою — 403 (перевірка доступу раніше за дублікат)."""
        data: dict = {**self.CREATE_DATA, 'name': supplier.name}
        response = regular_client.post(reverse('supplier_create'), data)
        assert response.status_code == 403


class TestSupplierUpdateView:
    """Тести для supplier_update view."""

    def test_regular_user_cannot_update_own_company(
        self, regular_client: Client, supplier: Supplier,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403 при спробі редагувати."""
        response = regular_client.get(reverse('supplier_update', kwargs={'pk': supplier.pk}))
        assert response.status_code == 403

    def test_regular_user_cannot_update_other_company(
        self, regular_client: Client, other_company: Company,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403 на чужу компанію (перевірка доступу раніше за компанію)."""
        other: Supplier = Supplier.objects.create(name='Чужий постачальник', company=other_company)
        response = regular_client.get(reverse('supplier_update', kwargs={'pk': other.pk}))
        assert response.status_code == 403

    def test_admin_user_can_update_own_company(
        self, admin_client: Client, supplier: Supplier,
    ) -> None:
        """Адміністратор може редагувати постачальника своєї компанії."""
        response = admin_client.get(reverse('supplier_update', kwargs={'pk': supplier.pk}))
        assert response.status_code == 200

    def test_admin_user_cannot_update_other_company(
        self, admin_client: Client, other_company: Company,
    ) -> None:
        """Адміністратор не може редагувати чужого постачальника (404)."""
        other: Supplier = Supplier.objects.create(name='Чужий постачальник', company=other_company)
        response = admin_client.get(reverse('supplier_update', kwargs={'pk': other.pk}))
        assert response.status_code == 404

    def test_update_success(self, admin_client: Client, supplier: Supplier) -> None:
        """Успішне оновлення постачальника адміністратором."""
        response = admin_client.post(
            reverse('supplier_update', kwargs={'pk': supplier.pk}), {
                'name': supplier.name,
                'contact_person': 'Нова контактна особа',
                'phone': '+380507771122',
                'email': 'updated@supplier.ua',
                'address': 'м. Одеса, вул. Нова, 5',
                'notes': 'Оновлені нотатки',
                'is_active': False,
                'company': supplier.company.pk,
            },
        )
        if response.status_code == 200 and response.context and response.context.get('form') and response.context['form'].errors:
            raise AssertionError(f'Form errors: {dict(response.context["form"].errors)}')

        supplier.refresh_from_db()
        assert supplier.contact_person == 'Нова контактна особа'
        assert supplier.is_active is False


class TestSupplierDeleteView:
    """Тести для supplier_delete view."""

    def test_regular_user_cannot_delete_own_company(
        self, regular_client: Client, supplier: Supplier,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403 при спробі видалення."""
        response = regular_client.post(reverse('supplier_delete', kwargs={'pk': supplier.pk}), follow=True)
        assert Supplier.objects.filter(pk=supplier.pk).exists()
        assert response.status_code == 403

    def test_regular_user_cannot_delete_other_company(
        self, regular_client: Client, other_company: Company,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403 на чужу компанію (перевірка доступу раніше за компанію)."""
        other: Supplier = Supplier.objects.create(name='Чужий на видалення', company=other_company)
        response = regular_client.post(reverse('supplier_delete', kwargs={'pk': other.pk}))
        assert response.status_code == 403
        assert Supplier.objects.filter(pk=other.pk).exists()

    def test_admin_user_can_delete_own_company(
        self, admin_client: Client, supplier: Supplier,
    ) -> None:
        """Адміністратор може видалити постачальника своєї компанії."""
        response = admin_client.post(reverse('supplier_delete', kwargs={'pk': supplier.pk}), follow=True)
        assert not Supplier.objects.filter(pk=supplier.pk).exists()
        assert response.status_code == 200

    def test_admin_user_cannot_delete_other_company(
        self, admin_client: Client, other_company: Company,
    ) -> None:
        """Адміністратор не може видалити чужого постачальника (404)."""
        other: Supplier = Supplier.objects.create(name='Чужий на видалення', company=other_company)
        response = admin_client.post(reverse('supplier_delete', kwargs={'pk': other.pk}))
        assert response.status_code == 404
        assert Supplier.objects.filter(pk=other.pk).exists()

    def test_delete_get_shows_confirmation_page(
        self, admin_client: Client, supplier: Supplier,
    ) -> None:
        """GET на delete показує сторінку підтвердження (для адміністратора)."""
        response = admin_client.get(reverse('supplier_delete', kwargs={'pk': supplier.pk}))
        assert response.status_code == 200
        assert response.context['supplier'] == supplier
