"""Наповнює довідник ролей (Role) базовими значеннями.

Використовується для первинного налаштування системи після
виконання міграцій на свіжій базі даних.

Приклад:
    python manage.py seed_roles
"""

from __future__ import annotations

from django.core.management import BaseCommand

from accounts.models import Role


ROLES_DATA: list[tuple[str, str]] = [
    ('director', 'Директор'),
    ('manager', 'Менеджер'),
    ('mechanic', 'Майстер'),
    ('accountant', 'Бухгалтер'),
    ('admin', 'Адміністратор'),
    ('purchaser', 'Закупівельник'),
    ('storekeeper', 'Складовщик'),
]


class Command(BaseCommand):
    """Команда для наповнення довідника ролей."""

    help = 'Наповнює довідник ролей базовими значеннями'

    def handle(self, *args: object, **options: object) -> None:
        """Створює записи Role, якщо вони ще не існують."""
        created_count: int = 0
        for codename, name in ROLES_DATA:
            _, was_created = Role.objects.get_or_create(
                codename=codename,
                defaults={'name': name},
            )
            if was_created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f'[OK] Роль "{name}" створено',
                ))
            else:
                self.stdout.write(f'[ ] Роль "{name}" вже існує')

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово! Створено {created_count} ролей.',
        ))
