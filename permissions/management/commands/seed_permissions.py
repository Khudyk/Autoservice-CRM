"""Команда для наповнення довідника модулів.

Приклад:
    python manage.py seed_permissions
    python manage.py seed_permissions --force  # перестворити модулі
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from permissions.models import Module

# Всі модулі (сторінки) системи
MODULES: list[dict[str, str]] = [
    {'codename': 'dashboard', 'name': 'Головна'},
    {'codename': 'companies', 'name': 'Компанії'},
    {'codename': 'clients', 'name': 'Клієнти'},
    {'codename': 'vehicles', 'name': 'Автомобілі'},
    {'codename': 'worktypes', 'name': 'Види робіт'},
    {'codename': 'suppliers', 'name': 'Постачальники'},
    {'codename': 'parts', 'name': 'Запчастини'},
    {'codename': 'purchases', 'name': 'Закупівля'},
    {'codename': 'payments', 'name': 'Розрахунки'},
    {'codename': 'workorders', 'name': 'Наряди'},
    {'codename': 'employees', 'name': 'Співробітники'},
    {'codename': 'administration', 'name': 'Адміністрування'},
    {'codename': 'permissions_manage', 'name': 'Керування правами'},
]


class Command(BaseCommand):
    """Наповнює довідник модулів системи."""

    help = 'Створює модулі системи для призначення прав співробітникам'

    def add_arguments(self, parser: Any) -> None:
        """Додає аргументи команди."""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Видалити існуючі модулі та створити заново',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Виконує наповнення."""
        force: bool = options.get('force', False)

        if force:
            Module.objects.all().delete()
            self.stdout.write(self.style.WARNING('Існуючі модулі видалено.'))

        self._create_modules()
        self.stdout.write(self.style.SUCCESS(
            f'Створено {Module.objects.count()} модулів.',
        ))

    @transaction.atomic
    def _create_modules(self) -> None:
        """Створює записи модулів, якщо їх ще немає."""
        for mod_data in MODULES:
            Module.objects.get_or_create(
                codename=mod_data['codename'],
                defaults={'name': mod_data['name']},
            )
