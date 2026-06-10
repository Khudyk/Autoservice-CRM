"""Тести моделі Company."""

from __future__ import annotations

import pytest
from django.db import models

from company.models import Company


class TestCompanyModel:
    """Тести для моделі Company."""

    def test_company_str_returns_name(self, db: None) -> None:
        """Перевіряє, що __str__ повертає назву компанії."""
        company: Company = Company.objects.create(name='Автосервіс Столиця')
        assert str(company) == 'Автосервіс Столиця'

    def test_company_creation_sets_timestamps(self, db: None) -> None:
        """Перевіряє, що created_at та updated_at заповнюються автоматично."""
        company: Company = Company.objects.create(
            name='Тестова компанія',
            email='test@company.com',
            phone='+380501234567',
        )
        assert company.created_at is not None
        assert company.updated_at is not None

    def test_company_default_blank_fields(self, db: None) -> None:
        """Перевіряє, що необов'язкові поля за замовчуванням порожні."""
        company: Company = Company.objects.create(name='Мінімальна компанія')
        assert company.email == ''
        assert company.phone == ''
        assert company.address == ''
        assert company.notes == ''

    def test_company_ordering_by_created_at_desc(self, db: None) -> None:
        """Перевіряє сортування за created_at спаданням."""
        Company.objects.create(name='Перша')
        Company.objects.create(name='Друга')
        companies = list(Company.objects.all())
        assert companies == sorted(companies, key=lambda c: c.created_at, reverse=True)

    def test_company_verbose_name(self, db: None) -> None:
        """Перевіряє Meta.verbose_name."""
        assert Company._meta.verbose_name == 'Компанія'
        assert Company._meta.verbose_name_plural == 'Компанії'

    def test_company_with_full_data(self, db: None) -> None:
        """Перевіряє створення компанії з усіма полями."""
        company: Company = Company.objects.create(
            name='Повна компанія',
            email='full@company.com',
            phone='+380501234567',
            address='м. Київ, вул. Тестова, 1',
            notes='Тестові нотатки',
        )
        assert company.name == 'Повна компанія'
        assert company.email == 'full@company.com'
        assert company.phone == '+380501234567'
        assert company.address == 'м. Київ, вул. Тестова, 1'
        assert company.notes == 'Тестові нотатки'

    def test_company_verbose_name_plural(self, db: None) -> None:
        """Перевіряє Meta.verbose_name_plural."""
        assert Company._meta.verbose_name_plural == 'Компанії'
