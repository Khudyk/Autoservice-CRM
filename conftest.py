"""Глобальні фікстури pytest, доступні в усіх тестах проєкту."""

from __future__ import annotations

from typing import Any

import pytest

from accounts.models import Role


@pytest.fixture
def roles(db: Any) -> None:
    """Гарантує наявність базових ролей у БД перед тестом.

    Створює 7 ролей, якщо вони ще не існують (перевірка .count()
    дозволяє використовувати одну фікстуру з будь-яким scope).
    """
    if Role.objects.count() == 0:
        roles_data: list[tuple[str, str]] = [
            ('director', 'Директор'),
            ('manager', 'Менеджер'),
            ('mechanic', 'Майстер'),
            ('accountant', 'Бухгалтер'),
            ('admin', 'Адміністратор'),
            ('purchaser', 'Закупівельник'),
            ('storekeeper', 'Складовщик'),
        ]
        for codename, name in roles_data:
            Role.objects.create(codename=codename, name=name)
