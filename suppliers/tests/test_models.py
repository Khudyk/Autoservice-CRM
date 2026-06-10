"""Тести моделі Supplier."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from suppliers.models import Supplier


class TestSupplierModel:
    """Тести для моделі Supplier."""

    def test_str_returns_name_and_company(self, supplier: Supplier) -> None:
        """Перевіряє, що __str__ повертає 'Назва — Компанія'."""
        expected: str = f'{supplier.name} — {supplier.company.name}'
        assert str(supplier) == expected

    def test_unique_name_per_company(self, supplier: Supplier, company) -> None:
        """Перевіряє унікальність назви в межах компанії."""
        with pytest.raises(IntegrityError):
            Supplier.objects.create(name=supplier.name, company=company)

    def test_same_name_different_company_allowed(
        self, supplier: Supplier, other_company,
    ) -> None:
        """Однакова назва може бути в різних компаніях."""
        s2: Supplier = Supplier.objects.create(
            name=supplier.name, company=other_company,
        )
        assert s2.pk is not None
        assert s2.company != supplier.company

    def test_default_is_active_true(self, supplier: Supplier) -> None:
        """Новий запис активний за замовчуванням."""
        assert supplier.is_active is True

    def test_creation_sets_timestamps(self, supplier: Supplier) -> None:
        """created_at та updated_at заповнюються автоматично."""
        assert supplier.created_at is not None
        assert supplier.updated_at is not None

    def test_ordering_by_name(self, company) -> None:
        """Постачальники сортуються за назвою за замовчуванням."""
        Supplier.objects.create(name='Яблуко', company=company)
        Supplier.objects.create(name='Апельсин', company=company)
        names = [s.name for s in Supplier.objects.filter(company=company)]
        assert names == sorted(names)

    def test_blank_fields_default_to_empty_string(self, company) -> None:
        """Необов'язкові поля за замовчуванням — порожні рядки."""
        s: Supplier = Supplier.objects.create(
            name='Мінімальний постачальник', company=company,
        )
        assert s.contact_person == ''
        assert s.phone == ''
        assert s.email == ''
        assert s.address == ''
        assert s.notes == ''
