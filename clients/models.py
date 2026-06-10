"""Модель клієнта автосервісу."""

from __future__ import annotations

from django.db import models


class Client(models.Model):
    """Клієнт автосервісу — фізична або юридична особа.

    Кожен клієнт прив'язаний до компанії (data isolation).
    Може мати декілька автомобілів (Vehicle.client).
    """

    first_name = models.CharField(
        "Ім'я / Назва",
        max_length=255,
        db_index=True,
        blank=True,
        default='',
    )
    last_name = models.CharField(
        'Прізвище',
        max_length=255,
        db_index=True,
        blank=True,
        default='',
    )
    phone = models.CharField(
        'Телефон',
        max_length=20,
    )
    email = models.EmailField(
        'Email',
        max_length=254,
        blank=True,
        default='',
    )
    notes = models.TextField(
        'Нотатки',
        blank=True,
        default='',
        help_text='Додаткова інформація про клієнта',
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='clients',
        verbose_name='Компанія',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Клієнт'
        verbose_name_plural = 'Клієнти'
        ordering = ['last_name', 'first_name']

    def __str__(self) -> str:
        """Повертає рядкове представлення: ПІБ (телефон)."""
        full: str = f'{self.last_name} {self.first_name}'.strip()
        if not full:
            full = self.first_name or self.last_name or '(без імені)'
        return f'{full} ({self.phone})'

    def get_full_name(self) -> str:
        """Повертає повне ім'я клієнта.

        Для фізичних осіб: Прізвище Ім'я.
        Для юридичних осіб: Назва (first_name).
        """
        if self.last_name:
            return f'{self.last_name} {self.first_name}'.strip()
        return self.first_name or '(без імені)'
