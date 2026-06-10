"""Тести моделі WorkType."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from worktypes.models import WorkType


class TestWorkTypeModel:
    """Тести для моделі WorkType."""

    def test_worktype_str_returns_name_and_company(
        self,
        worktype: WorkType,
    ) -> None:
        """Перевіряє, що __str__ повертає 'Назва — Компанія'."""
        expected: str = f'{worktype.name} — {worktype.company.name}'
        assert str(worktype) == expected

    def test_unique_name_per_company(
        self,
        worktype: WorkType,
        company,
    ) -> None:
        """Перевіряє унікальність назви в межах компанії."""
        with pytest.raises(IntegrityError):
            WorkType.objects.create(
                name='Заміна масла',
                company=company,
            )

    def test_same_name_different_company_allowed(
        self,
        worktype: WorkType,
        other_company,
    ) -> None:
        """Однакова назва може бути в різних компаніях."""
        w2: WorkType = WorkType.objects.create(
            name='Заміна масла',
            company=other_company,
        )
        assert w2.pk is not None
        assert w2.name == worktype.name
        assert w2.company != worktype.company

    def test_default_category_is_other(
        self,
        company,
    ) -> None:
        """Категорія за замовчуванням — 'Інше'."""
        w: WorkType = WorkType.objects.create(
            name='Тестова робота',
            company=company,
        )
        assert w.category == WorkType.Category.OTHER

    def test_default_is_active_true(
        self,
        worktype: WorkType,
    ) -> None:
        """Новий запис активний за замовчуванням."""
        assert worktype.is_active is True

    def test_worktype_creation_sets_timestamps(
        self,
        worktype: WorkType,
    ) -> None:
        """created_at та updated_at заповнюються автоматично."""
        assert worktype.created_at is not None
        assert worktype.updated_at is not None

    def test_worktype_ordering_by_name(
        self,
        company,
    ) -> None:
        """Роботи сортуються за назвою за замовчуванням."""
        WorkType.objects.create(name='Яблуко', company=company)
        WorkType.objects.create(name='Апельсин', company=company)
        names = [w.name for w in WorkType.objects.filter(company=company)]
        assert names == sorted(names)

    def test_worktype_description_blank_by_default(
        self,
        company,
    ) -> None:
        """Опис роботи за замовчуванням — порожній рядок."""
        wt: WorkType = WorkType.objects.create(
            name='Робота без опису',
            company=company,
        )
        assert wt.description == ''

    def test_worktype_category_all_choices_work(
        self,
        company,
    ) -> None:
        """Перевіряє всі категорії видів робіт."""
        for category_value, _ in WorkType.Category.choices:
            wt: WorkType = WorkType.objects.create(
                name=f'Робота_{category_value}',
                category=category_value,
                company=company,
            )
            assert wt.category == category_value

    def test_worktype_str_with_different_company(
        self,
        worktype: WorkType,
    ) -> None:
        """Рядкове представлення містить назву компанії."""
        assert worktype.company.name in str(worktype)

    def test_worktype_is_active_can_be_set_to_false(
        self,
        company,
    ) -> None:
        """Можна деактивувати вид роботи."""
        wt: WorkType = WorkType.objects.create(
            name='Застаріла робота',
            company=company,
            is_active=False,
        )
        assert wt.is_active is False

    def test_worktype_multiple_companies_have_separate_instances(
        self,
        company,
        other_company,
    ) -> None:
        """Однакова назва роботи в різних компаніях — різні записи."""
        wt1: WorkType = WorkType.objects.create(
            name='Діагностика',
            company=company,
        )
        wt2: WorkType = WorkType.objects.create(
            name='Діагностика',
            company=other_company,
        )
        assert wt1.pk != wt2.pk
        assert wt1.company != wt2.company
