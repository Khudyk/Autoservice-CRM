"""Тести management command seed_roles."""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command

from accounts.models import Role


class TestSeedRolesCommand:
    """Тести для команди seed_roles."""

    def test_command_creates_roles(self, db: Any) -> None:
        """Команда створює 7 базових ролей."""
        out: StringIO = StringIO()
        call_command('seed_roles', stdout=out)
        output: str = out.getvalue()

        assert 'Створено' in output
        assert Role.objects.count() == 7
        assert Role.objects.filter(codename='director').exists()
        assert Role.objects.filter(codename='manager').exists()
        assert Role.objects.filter(codename='mechanic').exists()
        assert Role.objects.filter(codename='accountant').exists()
        assert Role.objects.filter(codename='admin').exists()
        assert Role.objects.filter(codename='purchaser').exists()
        assert Role.objects.filter(codename='storekeeper').exists()

    def test_command_is_idempotent(self, db: Any) -> None:
        """Повторний запуск команди не створює дублікатів."""
        call_command('seed_roles', stdout=StringIO())
        first_count: int = Role.objects.count()

        out: StringIO = StringIO()
        call_command('seed_roles', stdout=out)
        second_count: int = Role.objects.count()

        assert first_count == second_count == 7
        assert 'вже існує' in out.getvalue()

    def test_command_creates_correct_role_codenames(self, db: Any) -> None:
        """Команда створює ролі з правильними codename."""
        call_command('seed_roles', stdout=StringIO())

        expected_codenames: set[str] = {
            'director', 'manager', 'mechanic', 'accountant',
            'admin', 'purchaser', 'storekeeper',
        }
        actual_codenames: set[str] = set(
            Role.objects.values_list('codename', flat=True),
        )
        assert actual_codenames == expected_codenames

    def test_command_creates_correct_role_names(self, db: Any) -> None:
        """Команда створює ролі з правильними назвами."""
        call_command('seed_roles', stdout=StringIO())

        assert Role.objects.get(codename='director').name == 'Директор'
        assert Role.objects.get(codename='manager').name == 'Менеджер'
        assert Role.objects.get(codename='mechanic').name == 'Майстер'
        assert Role.objects.get(codename='admin').name == 'Адміністратор'
