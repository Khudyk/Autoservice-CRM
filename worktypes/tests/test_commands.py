"""Тести management command seed_worktypes."""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command

from company.models import Company
from worktypes.models import WorkType


class TestSeedWorktypesCommand:
    """Тести для команди seed_worktypes."""

    @pytest.fixture
    def company(self, db: Any) -> Company:
        """Створює компанію з назвою «Автосервіс Столиця»."""
        return Company.objects.create(name='Автосервіс Столиця')

    def test_command_creates_worktypes(self, company: Company) -> None:
        """Команда створює типовий перелік робіт."""
        out: StringIO = StringIO()
        call_command('seed_worktypes', stdout=out)
        output: str = out.getvalue()

        # Перевіряємо, що щось створено
        assert 'створено' in output or 'пропущено' in output

        # Має бути 51 вид робіт
        assert WorkType.objects.filter(company=company).count() == 51

    def test_command_is_idempotent(self, company: Company) -> None:
        """Повторний запуск команди не створює дублікатів."""
        call_command('seed_worktypes', stdout=StringIO())
        first_count: int = WorkType.objects.filter(company=company).count()

        out: StringIO = StringIO()
        call_command('seed_worktypes', stdout=out)
        second_count: int = WorkType.objects.filter(company=company).count()

        assert first_count == second_count == 51
        assert 'пропущено' in out.getvalue()

    def test_command_with_company_id(self, company: Company) -> None:
        """Команда з --company працює для вказаної компанії."""
        out: StringIO = StringIO()
        call_command('seed_worktypes', company=company.pk, stdout=out)
        assert WorkType.objects.filter(company=company).count() == 51

    def test_command_company_not_found(self, company: Company) -> None:
        """Команда з неіснуючим company ID виводить помилку."""
        out: StringIO = StringIO()
        call_command('seed_worktypes', company=99999, stderr=out)
        assert 'не знайдено' in out.getvalue()

    def test_command_no_default_company(self, db: Any) -> None:
        """Команда без компанії за замовчуванням виводить помилку."""
        out: StringIO = StringIO()
        call_command('seed_worktypes', stderr=out)
        assert 'не знайдено' in out.getvalue()

    def test_command_force_updates_existing(self, company: Company) -> None:
        """Команда з --force оновлює існуючі записи."""
        # Змінюємо існуючий запис
        wt: WorkType = WorkType.objects.create(
            name='Заміна моторної оливи',
            description='Старий опис',
            company=company,
        )
        wt.description = 'Старий опис'
        wt.save()

        out: StringIO = StringIO()
        call_command('seed_worktypes', force=True, stdout=out, stderr=StringIO())
        output: str = out.getvalue()

        # Перевіряємо, що запис оновлено
        wt.refresh_from_db()
        assert wt.description != 'Старий опис'
        assert 'оновлено' in output or 'створено' in output or 'пропущено' in output
