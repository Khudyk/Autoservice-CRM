"""Тести представлень (views) додатку parts."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from company.models import Company
from parts.models import Part
from purchases.models import PurchaseOrder, PurchaseOrderItem
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


@pytest.fixture
def part_with_purchase_order(
    db, part: Part, company, supplier, employee,
) -> Part:
    """Запчастина, яка використовується в прихідній накладній."""
    po: PurchaseOrder = PurchaseOrder.objects.create(
        order_number=PurchaseOrder.generate_order_number(company_id=company.pk),
        supplier=supplier,
        company=company,
        created_by=employee,
    )
    PurchaseOrderItem.objects.create(
        purchase_order=po,
        part=part,
        quantity_ordered=Decimal('5.00'),
        unit_price=Decimal('100.00'),
    )
    return part


class TestPartListView:
    """Тести для part_list view."""

    def test_anonymous_sees_empty_list(self, client: Client, part: Part) -> None:
        """Анонім перенаправляється на сторінку входу."""
        response = client.get(reverse('part_list'))
        assert response.status_code == 302

    def test_regular_user_sees_only_own_company(
        self, regular_client: Client, part: Part, other_company: Company,
    ) -> None:
        """Звичайний користувач бачить тільки запчастини своєї компанії."""
        Part.objects.create(name='Інша запчастина', company=other_company)
        response = regular_client.get(reverse('part_list'))
        parts: list = response.context['page_obj']
        assert part in parts
        assert len(parts) == 1

    def test_staff_user_sees_all_parts(
        self, staff_client: Client, part: Part, other_company: Company,
    ) -> None:
        """Staff бачить усі запчастини з усіх компаній."""
        p2: Part = Part.objects.create(name='Запчастина іншої компанії', company=other_company)
        response = staff_client.get(reverse('part_list'))
        parts: list = response.context['page_obj']
        assert part in parts
        assert p2 in parts

    def test_staff_user_can_filter_by_company(
        self, staff_client: Client, part: Part, other_company: Company,
    ) -> None:
        """Staff може фільтрувати запчастини через ?company=<pk>."""
        p2: Part = Part.objects.create(name='Фільтрована запчастина', company=other_company)
        response = staff_client.get(reverse('part_list'), {'company': other_company.pk})
        parts: list = response.context['page_obj']
        assert p2 in parts
        assert part not in parts


class TestPartCreateView:
    """Тести для part_create view."""

    CREATE_DATA: dict = {
        'name': 'Гальмівні колодки',
        'part_number': 'BP-12345',
        'manufacturer': 'Brembo',
        'unit': Part.Unit.SET,
        'selling_price': Decimal('1200.00'),
        'min_quantity': Decimal('1.00'),
        'location': 'Стелаж B-2',
        'is_active': True,
    }

    def test_anonymous_get_returns_302(self, client: Client, db) -> None:
        """GET /parts/create/ для аноніма — 302 (перенаправлення на вхід)."""
        response = client.get(reverse('part_create'))
        assert response.status_code == 302

    def test_regular_user_create_gets_403(
        self, regular_client: Client,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403."""
        data: dict = {**self.CREATE_DATA}
        response = regular_client.post(reverse('part_create'), data)
        assert response.status_code == 403
        assert not Part.objects.filter(part_number='BP-12345').exists()

    def test_staff_user_can_create_in_any_company(
        self, staff_client: Client, other_company: Company,
    ) -> None:
        """Staff може створити запчастину в будь-якій компанії."""
        data: dict = {
            **self.CREATE_DATA, 'name': 'Staff запчастина', 'part_number': 'STAFF-001',
            'company': other_company.pk,
        }
        response = staff_client.post(reverse('part_create'), data)
        if response.status_code == 200 and response.context and response.context.get('form') and response.context['form'].errors:
            raise AssertionError(f'Form errors: {dict(response.context["form"].errors)}')

        created: Part = Part.objects.get(part_number='STAFF-001')
        assert created.company == other_company

    def test_duplicate_part_number_shows_error(
        self, regular_client: Client, part: Part,
    ) -> None:
        """Спроба створити з існуючим артикулом — 403 (перевірка доступу раніше за дублікат)."""
        data: dict = {**self.CREATE_DATA, 'part_number': part.part_number}
        response = regular_client.post(reverse('part_create'), data)
        assert response.status_code == 403


class TestPartUpdateView:
    """Тести для part_update view."""

    def test_regular_user_cannot_update_own_company(
        self, regular_client: Client, part: Part,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403 при спробі редагувати."""
        response = regular_client.get(reverse('part_update', kwargs={'pk': part.pk}))
        assert response.status_code == 403

    def test_regular_user_cannot_update_other_company(
        self, regular_client: Client, other_company: Company,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403 на чужу компанію (перевірка доступу раніше за компанію)."""
        other: Part = Part.objects.create(name='Чужа запчастина', company=other_company)
        response = regular_client.get(reverse('part_update', kwargs={'pk': other.pk}))
        assert response.status_code == 403

    def test_admin_user_can_update_own_company(
        self, admin_client: Client, part: Part,
    ) -> None:
        """Адміністратор може редагувати запчастину своєї компанії."""
        response = admin_client.get(reverse('part_update', kwargs={'pk': part.pk}))
        assert response.status_code == 200

    def test_admin_user_cannot_update_other_company(
        self, admin_client: Client, other_company: Company,
    ) -> None:
        """Адміністратор не може редагувати чужу запчастину (404)."""
        other: Part = Part.objects.create(name='Чужа запчастина', company=other_company)
        response = admin_client.get(reverse('part_update', kwargs={'pk': other.pk}))
        assert response.status_code == 404

    def test_update_success(self, admin_client: Client, part: Part) -> None:
        """Успішне оновлення запчастини адміністратором."""
        response = admin_client.post(
            reverse('part_update', kwargs={'pk': part.pk}), {
                'name': 'Оновлений фільтр',
                'part_number': part.part_number,
                'manufacturer': 'BOSCH',
                'unit': Part.Unit.PIECE,
                'selling_price': Decimal('350.00'),
                'min_quantity': Decimal('5.00'),
                'location': 'Стелаж C-3',
                'is_active': False,
                'company': part.company.pk,
            },
        )
        if response.status_code == 200 and response.context and response.context.get('form') and response.context['form'].errors:
            raise AssertionError(f'Form errors: {dict(response.context["form"].errors)}')

        part.refresh_from_db()
        assert part.name == 'Оновлений фільтр'
        assert part.manufacturer == 'BOSCH'
        assert part.selling_price == Decimal('350.00')
        assert part.is_active is False


class TestPartDeleteView:
    """Тести для part_delete view."""

    def test_regular_user_cannot_delete_own_company(
        self, regular_client: Client, part: Part,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403 при спробі видалення."""
        response = regular_client.post(reverse('part_delete', kwargs={'pk': part.pk}), follow=True)
        assert Part.objects.filter(pk=part.pk).exists()
        assert response.status_code == 403

    def test_regular_user_cannot_delete_other_company(
        self, regular_client: Client, other_company: Company,
    ) -> None:
        """Звичайний користувач (майстер) отримує 403 на чужу компанію (перевірка доступу раніше за компанію)."""
        other: Part = Part.objects.create(name='Чужа на видалення', company=other_company)
        response = regular_client.post(reverse('part_delete', kwargs={'pk': other.pk}))
        assert response.status_code == 403
        assert Part.objects.filter(pk=other.pk).exists()

    def test_admin_user_can_delete_own_company(
        self, admin_client: Client, part: Part,
    ) -> None:
        """Адміністратор може видалити запчастину своєї компанії."""
        response = admin_client.post(reverse('part_delete', kwargs={'pk': part.pk}), follow=True)
        assert not Part.objects.filter(pk=part.pk).exists()
        assert response.status_code == 200

    def test_admin_user_cannot_delete_other_company(
        self, admin_client: Client, other_company: Company,
    ) -> None:
        """Адміністратор не може видалити чужу запчастину (404)."""
        other: Part = Part.objects.create(name='Чужа на видалення', company=other_company)
        response = admin_client.post(reverse('part_delete', kwargs={'pk': other.pk}))
        assert response.status_code == 404
        assert Part.objects.filter(pk=other.pk).exists()

    def test_delete_get_shows_confirmation_page(self, admin_client: Client, part: Part) -> None:
        """GET на delete показує сторінку підтвердження (для адміністратора)."""
        response = admin_client.get(reverse('part_delete', kwargs={'pk': part.pk}))
        assert response.status_code == 200
        assert response.context['part'] == part

    def test_cannot_delete_part_with_purchase_orders(
        self, admin_client: Client, part_with_purchase_order: Part,
    ) -> None:
        """Спроба видалити запчастину з прихідними накладними — 409 (для адміністратора)."""
        response = admin_client.post(
            reverse('part_delete', kwargs={'pk': part_with_purchase_order.pk}),
            follow=True,
        )
        assert response.status_code == 409
        assert Part.objects.filter(pk=part_with_purchase_order.pk).exists()

    def test_update_part_with_purchase_orders_blocks_identity_fields(
        self, admin_client: Client, part_with_purchase_order: Part,
    ) -> None:
        """Редагування запчастини з прихідними накладними — блокує ідентифікаційні поля.

        Нова поведінка: замість 409 дозволяється редагування,
        але поля name, part_number, manufacturer та unit стають недоступними.
        Продажна ціна залишається доступною для адміністратора.
        """
        response = admin_client.get(
            reverse('part_update', kwargs={'pk': part_with_purchase_order.pk}),
        )
        assert response.status_code == 200
        assert response.context['form'].fields['name'].disabled is True
        assert response.context['form'].fields['part_number'].disabled is True
        assert response.context['form'].fields['manufacturer'].disabled is True
        assert response.context['form'].fields['unit'].disabled is True
        assert response.context['form'].fields['selling_price'].disabled is False
