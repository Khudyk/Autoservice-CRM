"""Тести представлень (views) додатку purchases — доступ, DatabaseError, ролі."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.db import DatabaseError
from django.db.models.query import QuerySet
from django.test import Client
from django.urls import reverse

from accounts.models import Employee, Role
from company.models import Company
from parts.models import Part
from permissions.models import EmployeePermission, Module
from purchases.models import PurchaseOrder, PurchaseOrderItem
from suppliers.models import Supplier


# =============================================================================
# БАЗОВІ ФІКСТУРИ
# =============================================================================


@pytest.fixture(scope='module')
def company(django_db_blocker: None) -> Company:
    """Створює тестову компанію (module-scoped)."""
    with django_db_blocker.unblock():
        return Company.objects.create(
            name="Тестова компанія",
            email="test@company.com",
            phone="+380501234567",
        )


@pytest.fixture(scope='module')
def other_company(django_db_blocker: None) -> Company:
    """Інша компанія для тестів ізоляції (module-scoped)."""
    with django_db_blocker.unblock():
        return Company.objects.create(name="Інша компанія")


@pytest.fixture
def employee(roles, company: Company) -> Employee:
    """Співробітник-механік."""
    user = User.objects.create_user(username="testuser", password="testpass123")
    emp = Employee.objects.create(user=user, company=company, phone="+380501112233")
    emp.roles.set([Role.objects.get(codename="mechanic")])
    return emp


@pytest.fixture
def supplier(company: Company) -> Supplier:
    """Тестовий постачальник."""
    return Supplier.objects.create(
        name="ТОВ Автозапчастини",
        contact_person="Іван Петрович",
        phone="+380501234567",
        company=company,
    )


@pytest.fixture
def part(company: Company) -> Part:
    """Тестова запчастина."""
    return Part.objects.create(
        name="Масляний фільтр",
        part_number="OC 260",
        manufacturer="MANN-FILTER",
        unit=Part.Unit.PIECE,
        selling_price=Decimal("250.00"),
        min_quantity=Decimal("2.00"),
        location="Стелаж A-1",
        company=company,
    )


@pytest.fixture
def draft_order(company: Company, supplier: Supplier, employee: Employee) -> PurchaseOrder:
    """Чернетка замовлення."""
    return PurchaseOrder.objects.create(
        order_number=PurchaseOrder.generate_order_number(company_id=company.pk),
        supplier=supplier,
        status=PurchaseOrder.Status.DRAFT,
        notes="Тестове замовлення",
        created_by=employee,
        company=company,
    )


@pytest.fixture
def draft_order_with_items(draft_order: PurchaseOrder, part: Part) -> PurchaseOrder:
    """Чернетка з однією позицією."""
    PurchaseOrderItem.objects.create(
        purchase_order=draft_order, part=part,
        quantity_ordered=Decimal("10.00"), unit_price=Decimal("150.00"),
    )
    return draft_order


@pytest.fixture
def ordered_order(draft_order_with_items: PurchaseOrder) -> PurchaseOrder:
    """Замовлення в статусі ORDERED."""
    draft_order_with_items.status = PurchaseOrder.Status.ORDERED
    draft_order_with_items.save(update_fields=["status"])
    return draft_order_with_items


# =============================================================================
# КЛІЄНТИ З РІЗНИМИ РОЛЯМИ
# =============================================================================


def _make_role_client(
    client: Client, roles, company: Company, role_name: str,
    permissions: list[tuple[str, list[str]]] | None = None,
) -> Client:
    """Допоміжна функція для створення клієнта з роллю.

    Args:
        permissions: Список кортежів (module_codename, [action, ...]).
    """
    user = User.objects.create_user(username=f"user_{role_name}", password="testpass123")
    emp = Employee.objects.create(user=user, company=company, phone="+380509990000")
    emp.roles.set([Role.objects.get(codename=role_name)])
    user.is_staff = False
    user.save()
    if permissions:
        for module_codename, actions in permissions:
            module, _ = Module.objects.get_or_create(
                codename=module_codename,
                defaults={'name': module_codename},
            )
            defaults: dict[str, bool] = {}
            for action in actions:
                defaults[f'can_{action}'] = True
            EmployeePermission.objects.update_or_create(
                employee=emp,
                module=module,
                defaults=defaults,
            )
    client.login(username=f"user_{role_name}", password="testpass123")
    return client


@pytest.fixture
def mechanic_client(client: Client, roles, company: Company) -> Client:
    """Клієнт-механік."""
    return _make_role_client(client, roles, company, "mechanic")


@pytest.fixture
def admin_client(client: Client, roles, company: Company) -> Client:
    """Клієнт-адміністратор."""
    return _make_role_client(
        client, roles, company, "admin",
        permissions=[
            ('purchases', ['read', 'create', 'edit', 'delete']),
            ('payments', ['read', 'create', 'edit', 'delete']),
        ],
    )


@pytest.fixture
def staff_client(client: Client, roles, company: Company) -> Client:
    """Клієнт-staff/superuser."""
    user = User.objects.create_user(
        username="staff_user", password="testpass123",
        is_staff=True, is_superuser=True,
    )
    Employee.objects.create(user=user, company=company, phone="+380509990001")
    user.is_staff = True
    user.is_superuser = True
    user.save()
    client.login(username="staff_user", password="testpass123")
    return client


@pytest.fixture
def manager_client(client: Client, roles, company: Company) -> Client:
    """Клієнт-менеджер."""
    return _make_role_client(
        client, roles, company, "manager",
        permissions=[
            ('purchases', ['read', 'create', 'edit']),
            ('payments', ['read', 'create', 'edit']),
        ],
    )


@pytest.fixture
def purchaser_client(client: Client, roles, company: Company) -> Client:
    """Клієнт-закупівельник."""
    return _make_role_client(
        client, roles, company, "purchaser",
        permissions=[
            ('purchases', ['read', 'create', 'edit']),
        ],
    )


@pytest.fixture
def storekeeper_client(client: Client, roles, company: Company) -> Client:
    """Клієнт-складовщик."""
    return _make_role_client(
        client, roles, company, "storekeeper",
        permissions=[
            ('purchases', ['read']),
        ],
    )


# =============================================================================
# ТЕСТИ
# =============================================================================


class TestPurchaseListView:
    """Список замовлень."""

    def test_anonymous_redirects(self, client: Client) -> None:
        """Анонім — 302."""
        assert client.get(reverse("purchase_list")).status_code == 302

    def test_mechanic_gets_403(self, mechanic_client: Client) -> None:
        """Механік — 403."""
        assert mechanic_client.get(reverse("purchase_list")).status_code == 403

    def test_admin_can_access(self, admin_client: Client) -> None:
        """Адмін — 200."""
        assert admin_client.get(reverse("purchase_list")).status_code == 200

    def test_manager_can_access(self, manager_client: Client) -> None:
        """Менеджер — 200."""
        assert manager_client.get(reverse("purchase_list")).status_code == 200

    def test_purchaser_can_access(self, purchaser_client: Client) -> None:
        """Закупівельник — 200."""
        assert purchaser_client.get(reverse("purchase_list")).status_code == 200

    def test_storekeeper_can_access(self, storekeeper_client: Client) -> None:
        """Складовщик — 200."""
        assert storekeeper_client.get(reverse("purchase_list")).status_code == 200

    def test_admin_sees_all_orders(
        self, staff_client: Client, company: Company, other_company: Company, supplier: Supplier,
    ) -> None:
        """Адмін бачить замовлення всіх компаній."""
        s2 = Supplier.objects.create(name="Інший", company=other_company)
        PurchaseOrder.objects.create(order_number="PO-01", supplier=supplier, company=company)
        PurchaseOrder.objects.create(order_number="PO-02", supplier=s2, company=other_company)
        response = staff_client.get(reverse("purchase_list"))
        assert response.status_code == 200
        assert len(list(response.context["page_obj"])) == 2


class TestPurchaseCreateView:
    """Створення замовлення."""

    def test_mechanic_gets_403(self, mechanic_client: Client) -> None:
        assert mechanic_client.get(reverse("purchase_create")).status_code == 403

    def test_admin_get_form(self, admin_client: Client) -> None:
        assert admin_client.get(reverse("purchase_create")).status_code == 200

    def test_admin_post_creates_order(
        self, admin_client: Client, company: Company, supplier: Supplier, part: Part,
    ) -> None:
        response = admin_client.post(reverse("purchase_create"), {
            "supplier": str(supplier.pk), "company": str(company.pk), "notes": "Test",
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1", "items-MAX_NUM_FORMS": "1000",
            "items-0-part": str(part.pk), "items-0-quantity_ordered": "5.00", "items-0-unit_price": "200.00",
        })
        assert response.status_code == 302
        assert PurchaseOrder.objects.count() == 1

    def test_storekeeper_cannot_create(
        self, storekeeper_client: Client, company: Company, supplier: Supplier, part: Part,
    ) -> None:
        response = storekeeper_client.post(reverse("purchase_create"), {
            "supplier": str(supplier.pk), "company": str(company.pk), "notes": "Test",
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1", "items-MAX_NUM_FORMS": "1000",
            "items-0-part": str(part.pk), "items-0-quantity_ordered": "2.00", "items-0-unit_price": "150.00",
        })
        assert response.status_code == 403
        assert PurchaseOrder.objects.count() == 0


class TestPurchaseDetailView:
    """Деталі замовлення."""

    def test_mechanic_gets_403(self, mechanic_client: Client, draft_order: PurchaseOrder) -> None:
        response = mechanic_client.get(reverse("purchase_detail", kwargs={"pk": draft_order.pk}))
        assert response.status_code == 403

    def test_admin_sees_detail(self, admin_client: Client, draft_order_with_items: PurchaseOrder) -> None:
        response = admin_client.get(reverse("purchase_detail", kwargs={"pk": draft_order_with_items.pk}))
        assert response.status_code == 200


class TestPurchaseUpdateView:
    """Редагування замовлення + DatabaseError."""

    def test_mechanic_gets_403(self, mechanic_client: Client, draft_order: PurchaseOrder) -> None:
        response = mechanic_client.get(reverse("purchase_update", kwargs={"pk": draft_order.pk}))
        assert response.status_code == 403

    def test_admin_get_form(self, admin_client: Client, draft_order: PurchaseOrder) -> None:
        response = admin_client.get(reverse("purchase_update", kwargs={"pk": draft_order.pk}))
        assert response.status_code == 200

    def test_admin_post_updates(self, admin_client: Client, draft_order_with_items: PurchaseOrder) -> None:
        item = draft_order_with_items.items.first()
        assert item is not None
        response = admin_client.post(
            reverse("purchase_update", kwargs={"pk": draft_order_with_items.pk}),
            data={
                "supplier": str(draft_order_with_items.supplier_id),
                "company": str(draft_order_with_items.company_id),
                "notes": "Оновлені нотатки",
                "items-TOTAL_FORMS": "4", "items-INITIAL_FORMS": "1",
                "items-MIN_NUM_FORMS": "1", "items-MAX_NUM_FORMS": "1000",
                "items-0-id": str(item.pk), "items-0-part": str(item.part_id),
                "items-0-quantity_ordered": str(item.quantity_ordered),
                "items-0-unit_price": str(item.unit_price),
            },
        )
        assert response.status_code == 302
        draft_order_with_items.refresh_from_db()
        assert draft_order_with_items.notes == "Оновлені нотатки"

    def test_admin_update_non_draft_returns_403(self, admin_client: Client, ordered_order: PurchaseOrder) -> None:
        response = admin_client.get(reverse("purchase_update", kwargs={"pk": ordered_order.pk}))
        assert response.status_code == 403

    def test_post_with_database_error_returns_409(self, admin_client: Client, draft_order: PurchaseOrder) -> None:
        """DatabaseError при select_for_update — 409 Conflict."""
        with patch.object(QuerySet, "select_for_update") as mock_select:
            mock_select.side_effect = DatabaseError("lock timeout")
            response = admin_client.post(
                reverse("purchase_update", kwargs={"pk": draft_order.pk}), {"notes": "test"},
            )
        assert response.status_code == 409

    def test_storekeeper_cannot_update(self, storekeeper_client: Client, draft_order: PurchaseOrder) -> None:
        response = storekeeper_client.get(reverse("purchase_update", kwargs={"pk": draft_order.pk}))
        assert response.status_code == 403


class TestPurchaseSubmitView:
    """Відправлення замовлення + DatabaseError."""

    def test_mechanic_gets_403(self, mechanic_client: Client, draft_order_with_items: PurchaseOrder) -> None:
        response = mechanic_client.post(reverse("purchase_submit", kwargs={"pk": draft_order_with_items.pk}))
        assert response.status_code == 403

    def test_admin_submit_changes_status(self, admin_client: Client, draft_order_with_items: PurchaseOrder) -> None:
        response = admin_client.post(reverse("purchase_submit", kwargs={"pk": draft_order_with_items.pk}))
        assert response.status_code == 302
        draft_order_with_items.refresh_from_db()
        assert draft_order_with_items.status == PurchaseOrder.Status.ORDERED

    def test_submit_without_items_returns_400(self, admin_client: Client, draft_order: PurchaseOrder) -> None:
        response = admin_client.post(reverse("purchase_submit", kwargs={"pk": draft_order.pk}))
        assert response.status_code == 400

    def test_submit_with_database_error_returns_409(self, admin_client: Client, draft_order_with_items: PurchaseOrder) -> None:
        with patch.object(QuerySet, "select_for_update") as mock_select:
            mock_select.side_effect = DatabaseError("lock timeout")
            response = admin_client.post(
                reverse("purchase_submit", kwargs={"pk": draft_order_with_items.pk}),
            )
        assert response.status_code == 409

    def test_storekeeper_cannot_submit(self, storekeeper_client: Client, draft_order_with_items: PurchaseOrder) -> None:
        response = storekeeper_client.post(reverse("purchase_submit", kwargs={"pk": draft_order_with_items.pk}))
        assert response.status_code == 403


class TestPurchaseDeleteView:
    """Видалення замовлення + DatabaseError."""

    def test_mechanic_gets_403(self, mechanic_client: Client, draft_order: PurchaseOrder) -> None:
        response = mechanic_client.post(reverse("purchase_delete", kwargs={"pk": draft_order.pk}))
        assert response.status_code == 403

    def test_delete_with_database_error_returns_409(self, admin_client: Client, draft_order: PurchaseOrder) -> None:
        with patch.object(QuerySet, "select_for_update") as mock_select:
            mock_select.side_effect = DatabaseError("lock timeout")
            response = admin_client.post(
                reverse("purchase_delete", kwargs={"pk": draft_order.pk}),
            )
        assert response.status_code == 409
