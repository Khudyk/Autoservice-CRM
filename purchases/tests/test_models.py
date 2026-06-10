"""Тести моделей додатку purchases."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.db.models import QuerySet

from accounts.models import Employee
from company.models import Company
from parts.models import Part
from purchases.models import PurchaseOrder, PurchaseOrderItem
from suppliers.models import Supplier


# =============================================================================
# ФІКСТУРИ (повторно використовувані)
# =============================================================================


@pytest.fixture
def roles_setup(db: None) -> None:
    """Гарантує наявність ролей (якщо ще не створені)."""
    from accounts.models import Role
    if Role.objects.count() == 0:
        for codename, name in [
            ("director", "Директор"),
            ("manager", "Менеджер"),
            ("mechanic", "Майстер"),
            ("accountant", "Бухгалтер"),
            ("admin", "Адміністратор"),
            ("purchaser", "Закупівельник"),
            ("storekeeper", "Складовщик"),
        ]:
            Role.objects.create(codename=codename, name=name)


@pytest.fixture
def company(db: Any) -> Company:
    """Створює тестову компанію."""
    return Company.objects.create(
        name="Тестова компанія",
        email="test@company.com",
        phone="+380501234567",
    )


@pytest.fixture
def other_company(db: Any) -> Company:
    """Створює іншу компанію для тестів ізоляції."""
    return Company.objects.create(name="Інша компанія")


@pytest.fixture
def supplier(company: Company) -> Supplier:
    """Створює постачальника в тій самій компанії."""
    return Supplier.objects.create(
        name="ТОВ Автозапчастини",
        contact_person="Іван Петрович",
        phone="+380501234567",
        company=company,
    )


@pytest.fixture
def employee(roles_setup, company: Company) -> Employee:
    """Створює тестового співробітника."""
    from django.contrib.auth.models import User
    from accounts.models import Role
    user = User.objects.create_user(username="testuser", password="testpass123")
    emp = Employee.objects.create(user=user, company=company, phone="+380501112233")
    emp.roles.set([Role.objects.get(codename="mechanic")])
    return emp


@pytest.fixture
def part(company: Company) -> Part:
    """Створює запчастину."""
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
    """Створює замовлення в статусі Чернетка."""
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
    """Чернетка з однією позицією (10 од. по 150 грн)."""
    PurchaseOrderItem.objects.create(
        purchase_order=draft_order,
        part=part,
        quantity_ordered=Decimal("10.00"),
        unit_price=Decimal("150.00"),
    )
    return draft_order


# =============================================================================
# ТЕСТИ МОДЕЛІ PurchaseOrder
# =============================================================================


class TestPurchaseOrderStatus:
    """Перевірка визначення статусів замовлення."""

    @pytest.mark.parametrize("status_attr, expected_value", [
        ("DRAFT", "draft"),
        ("ORDERED", "ordered"),
        ("PARTIALLY_RECEIVED", "partially_received"),
        ("RECEIVED", "received"),
        ("CANCELLED", "cancelled"),
    ])
    def test_status_choices_values(self, status_attr: str, expected_value: str) -> None:
        """Кожен статус має правильне значення для БД."""
        assert getattr(PurchaseOrder.Status, status_attr).value == expected_value

    @pytest.mark.parametrize("status_attr, expected_label", [
        ("DRAFT", "Чернетка"),
        ("ORDERED", "Замовлено"),
        ("PARTIALLY_RECEIVED", "Частково отримано"),
        ("RECEIVED", "Отримано"),
        ("CANCELLED", "Скасовано"),
    ])
    def test_status_choices_labels(self, status_attr: str, expected_label: str) -> None:
        """Кожен статус має правильний human-readable label."""
        assert getattr(PurchaseOrder.Status, status_attr).label == expected_label

    def test_default_status_is_draft(self, company: Company, supplier: Supplier) -> None:
        """Нове замовлення має статус DRAFT за замовчуванням."""
        order = PurchaseOrder(
            order_number="PO-00001", supplier=supplier, company=company,
        )
        assert order.status == PurchaseOrder.Status.DRAFT


class TestPurchaseOrderGenerateOrderNumber:
    """Перевірка генерації номерів замовлень."""

    def test_first_order_number(self, db: Any, company: Company) -> None:
        """Перше замовлення отримує PO-00001."""
        assert PurchaseOrder.generate_order_number(company_id=company.pk) == "PO-00001"

    def test_increments_sequentially(
        self, db: Any, company: Company, supplier: Supplier,
    ) -> None:
        """Наступне замовлення отримує збільшений номер."""
        PurchaseOrder.objects.create(
            order_number="PO-00001", supplier=supplier, company=company,
        )
        assert PurchaseOrder.generate_order_number(company_id=company.pk) == "PO-00002"

    def test_per_company_isolation(
        self, db: Any, company: Company, other_company: Company, supplier: Supplier,
    ) -> None:
        """Кожна компанія має власну нумерацію."""
        PurchaseOrder.objects.create(
            order_number="PO-00005", supplier=supplier, company=company,
        )
        assert PurchaseOrder.generate_order_number(company_id=company.pk) == "PO-00006"
        assert PurchaseOrder.generate_order_number(company_id=other_company.pk) == "PO-00001"

    def test_handles_non_po_prefix(
        self, db: Any, company: Company, supplier: Supplier,
    ) -> None:
        """Нестандартний префікс — рахунок скидається."""
        PurchaseOrder.objects.create(
            order_number="INV-00001", supplier=supplier, company=company,
        )
        assert PurchaseOrder.generate_order_number(company_id=company.pk) == "PO-00001"

    def test_handles_invalid_suffix(
        self, db: Any, company: Company, supplier: Supplier,
    ) -> None:
        """Якщо після PO- йде не число — рахунок починається з 1."""
        PurchaseOrder.objects.create(
            order_number="PO-ABC", supplier=supplier, company=company,
        )
        assert PurchaseOrder.generate_order_number(company_id=company.pk) == "PO-00001"


class TestPurchaseOrderTotalAmount:
    """Перевірка обчислення суми замовлення."""

    def test_empty_order_returns_zero(self, draft_order: PurchaseOrder) -> None:
        """Без позицій сума = 0."""
        assert draft_order.total_amount == Decimal("0.00")

    def test_with_single_item(self, draft_order_with_items: PurchaseOrder) -> None:
        """Одна позиція: 10 x 150 = 1500 грн."""
        assert draft_order_with_items.total_amount == Decimal("1500.00")

    def test_with_multiple_items(
        self, draft_order: PurchaseOrder, part: Part,
    ) -> None:
        """Дві позиції: 10x150 + 5x200 = 2500 грн."""
        PurchaseOrderItem.objects.create(
            purchase_order=draft_order, part=part,
            quantity_ordered=Decimal("10.00"), unit_price=Decimal("150.00"),
        )
        PurchaseOrderItem.objects.create(
            purchase_order=draft_order, part=part,
            quantity_ordered=Decimal("5.00"), unit_price=Decimal("200.00"),
        )
        assert draft_order.total_amount == Decimal("2500.00")


class TestPurchaseOrderIsEditable:
    """Перевірка is_editable."""

    @pytest.mark.parametrize("status, editable", [
        (PurchaseOrder.Status.DRAFT, True),
        (PurchaseOrder.Status.ORDERED, False),
        (PurchaseOrder.Status.PARTIALLY_RECEIVED, False),
        (PurchaseOrder.Status.RECEIVED, False),
        (PurchaseOrder.Status.CANCELLED, False),
    ])
    def test_is_editable_by_status(
        self, db: Any, status: str, editable: bool,
        company: Company, supplier: Supplier, employee: Employee,
    ) -> None:
        """Тільки DRAFT повертає True для is_editable."""
        order = PurchaseOrder.objects.create(
            order_number="PO-99999", supplier=supplier,
            status=status, created_by=employee, company=company,
        )
        assert order.is_editable is editable


class TestPurchaseOrderIsReceivable:
    """Перевірка is_receivable."""

    @pytest.mark.parametrize("status, receivable", [
        (PurchaseOrder.Status.DRAFT, False),
        (PurchaseOrder.Status.ORDERED, True),
        (PurchaseOrder.Status.PARTIALLY_RECEIVED, True),
        (PurchaseOrder.Status.RECEIVED, False),
        (PurchaseOrder.Status.CANCELLED, False),
    ])
    def test_is_receivable_by_status(
        self, db: Any, status: str, receivable: bool,
        company: Company, supplier: Supplier, employee: Employee,
    ) -> None:
        """Тільки ORDERED або PARTIALLY_RECEIVED."""
        order = PurchaseOrder.objects.create(
            order_number="PO-99999", supplier=supplier,
            status=status, created_by=employee, company=company,
        )
        assert order.is_receivable is receivable


class TestPurchaseOrderUniqueness:
    """Унікальність номера замовлення."""

    def test_unique_order_number_per_company(
        self, db: Any, company: Company, supplier: Supplier, employee: Employee,
    ) -> None:
        """Унікальний в межах компанії."""
        PurchaseOrder.objects.create(
            order_number="PO-00001", supplier=supplier,
            company=company, created_by=employee,
        )
        with pytest.raises(Exception):
            PurchaseOrder.objects.create(
                order_number="PO-00001", supplier=supplier,
                company=company, created_by=employee,
            )

    def test_same_number_different_companies_allowed(
        self, db: Any, company: Company, other_company: Company,
        supplier: Supplier, employee: Employee,
    ) -> None:
        """Однаковий номер в різних компаніях дозволено."""
        PurchaseOrder.objects.create(
            order_number="PO-00001", supplier=supplier,
            company=company, created_by=employee,
        )
        order2 = PurchaseOrder.objects.create(
            order_number="PO-00001", supplier=supplier,
            company=other_company, created_by=employee,
        )
        assert order2.pk is not None

    def test_str_representation(self, draft_order: PurchaseOrder) -> None:
        """__str__ повертає номер замовлення та постачальника."""
        result = str(draft_order)
        assert draft_order.order_number in result
        assert draft_order.supplier.name in result


# =============================================================================
# ТЕСТИ МОДЕЛІ PurchaseOrderItem
# =============================================================================


class TestPurchaseOrderItem:
    """Властивості позиції замовлення."""

    def test_total_price(self, db: Any, draft_order: PurchaseOrder, part: Part) -> None:
        """total_price = quantity_ordered x unit_price."""
        item = PurchaseOrderItem.objects.create(
            purchase_order=draft_order, part=part,
            quantity_ordered=Decimal("10.00"), unit_price=Decimal("150.00"),
        )
        assert item.total_price == Decimal("1500.00")

    def test_remaining_to_receive(
        self, db: Any, draft_order: PurchaseOrder, part: Part,
    ) -> None:
        """remaining_to_receive = quantity_ordered - quantity_received."""
        item = PurchaseOrderItem.objects.create(
            purchase_order=draft_order, part=part,
            quantity_ordered=Decimal("10.00"), quantity_received=Decimal("3.00"),
            unit_price=Decimal("150.00"),
        )
        assert item.remaining_to_receive == Decimal("7.00")

    def test_remaining_to_receive_when_fully_received(
        self, db: Any, draft_order: PurchaseOrder, part: Part,
    ) -> None:
        """Коли все отримано, залишок = 0."""
        item = PurchaseOrderItem.objects.create(
            purchase_order=draft_order, part=part,
            quantity_ordered=Decimal("10.00"), quantity_received=Decimal("10.00"),
            unit_price=Decimal("150.00"),
        )
        assert item.remaining_to_receive == Decimal("0.00")

    def test_str_representation(
        self, db: Any, draft_order: PurchaseOrder, part: Part,
    ) -> None:
        """__str__ повертає назву, кількість та ціну."""
        item = PurchaseOrderItem.objects.create(
            purchase_order=draft_order, part=part,
            quantity_ordered=Decimal("10.00"), unit_price=Decimal("150.00"),
        )
        result = str(item)
        assert part.name in result
        assert "10" in result
        assert "150" in result
