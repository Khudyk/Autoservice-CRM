"""Глобальні фікстури pytest, доступні в усіх тестах проєкту."""

from __future__ import annotations

from typing import Any

import pytest

from accounts.models import Role


@pytest.fixture
def roles(db: Any) -> None:
    """Гарантує наявність базових ролей у БД перед тестом.

    Створює 7 ролей, якщо вони ще не існують (перевірка .count()
    дозволяє безпечно використовувати з --reuse-db).
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
        Role.objects.bulk_create([
            Role(codename=codename, name=name)
            for codename, name in roles_data
        ])
