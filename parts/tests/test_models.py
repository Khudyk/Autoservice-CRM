"""Тести моделі Part."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError

from parts.models import Part


class TestPartModel:
    """Тести для моделі Part."""

    def test_str_with_part_number(self, part: Part) -> None:
        """__str__ з артикулом: 'Назва (Артикул) — Компанія'."""
        expected: str = f'{part.name} ({part.part_number}) — {part.company.name}'
        assert str(part) == expected

    def test_str_without_part_number(self, company) -> None:
        """__str__ без артикула: 'Назва — Компанія'."""
        p: Part = Part.objects.create(name='Гайка', company=company)
        expected: str = f'{p.name} — {p.company.name}'
        assert str(p) == expected

    def test_unique_part_number_per_company(self, part: Part, company) -> None:
        """Перевіряє унікальність артикула в межах компанії."""
        with pytest.raises(IntegrityError):
            Part.objects.create(name='Інша назва', part_number='OC 260', company=company)

    def test_same_part_number_different_company_allowed(
        self, part: Part, other_company,
    ) -> None:
        """Однаковий артикул може бути в різних компаніях."""
        p2: Part = Part.objects.create(
            name='Масляний фільтр', part_number='OC 260', company=other_company,
        )
        assert p2.pk is not None
        assert p2.part_number == part.part_number
        assert p2.company != part.company

    def test_default_unit_is_piece(self, company) -> None:
        """Одиниця виміру за замовчуванням — 'шт'."""
        p: Part = Part.objects.create(name='Тестова запчастина', company=company)
        assert p.unit == Part.Unit.PIECE

    def test_default_is_active_true(self, part: Part) -> None:
        """Нова запчастина активна за замовчуванням."""
        assert part.is_active is True

    def test_default_prices_zero(self, company) -> None:
        """Ціна продажу за замовчуванням — 0."""
        p: Part = Part.objects.create(name='Тест', company=company)
        assert p.selling_price == Decimal('0.00')
        assert p.min_quantity == Decimal('0.00')

    def test_creation_sets_timestamps(self, part: Part) -> None:
        """created_at та updated_at заповнюються автоматично."""
        assert part.created_at is not None
        assert part.updated_at is not None

    def test_ordering_by_name(self, company) -> None:
        """Запчастини сортуються за назвою за замовчуванням."""
        Part.objects.create(name='Яблуко', part_number='P-001', company=company)
        Part.objects.create(name='Апельсин', part_number='P-002', company=company)
        names = [p.name for p in Part.objects.filter(company=company)]
        assert names == sorted(names)

    def test_has_purchase_orders_false_by_default(self, part: Part) -> None:
        """Нова запчастина без прихідних накладних."""
        assert part.has_purchase_orders is False

    def test_has_purchase_orders_true_when_used_in_order(
        self, part: Part, company, supplier, employee,
    ) -> None:
        """Запчастина, що є в прихідній накладній."""
        from purchases.models import PurchaseOrder, PurchaseOrderItem
        po: PurchaseOrder = PurchaseOrder.objects.create(
            order_number=PurchaseOrder.generate_order_number(company_id=company.pk),
            supplier=supplier,
            company=company,
            created_by=employee,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            part=part,
            quantity_ordered=5,
            unit_price=Decimal('100.00'),
        )
        assert part.has_purchase_orders is True

    def test_delete_protected_when_has_purchase_orders(
        self, part: Part, company, supplier, employee,
    ) -> None:
        """Part з прихідними накладними не можна видалити (ProtectedError)."""
        from django.db.models import ProtectedError
        from purchases.models import PurchaseOrder, PurchaseOrderItem
        po: PurchaseOrder = PurchaseOrder.objects.create(
            order_number=PurchaseOrder.generate_order_number(company_id=company.pk),
            supplier=supplier,
            company=company,
            created_by=employee,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            part=part,
            quantity_ordered=3,
            unit_price=Decimal('50.00'),
        )
        with pytest.raises(ProtectedError):
            part.delete()
