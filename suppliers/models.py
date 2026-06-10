"""Моделі додатку suppliers — постачальники запчастин та матеріалів."""

from __future__ import annotations

from django.db import models


class Supplier(models.Model):
    """Модель постачальника запчастин та матеріалів для автосервісу.

    Кожен постачальник прив'язаний до компанії (data isolation).
    """

    name = models.CharField(
        'Назва постачальника',
        max_length=255,
        db_index=True,
    )
    contact_person = models.CharField(
        'Контактна особа',
        max_length=255,
        blank=True,
        help_text='ПІБ контактної особи',
    )
    phone = models.CharField(
        'Телефон',
        max_length=20,
        blank=True,
    )
    email = models.EmailField(
        'Email',
        blank=True,
    )
    address = models.TextField(
        'Адреса',
        blank=True,
        help_text='Фактична адреса постачальника',
    )
    notes = models.TextField(
        'Нотатки',
        blank=True,
        help_text='Додаткова інформація про постачальника',
    )
    is_active = models.BooleanField(
        'Активний',
        default=True,
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='suppliers',
        verbose_name='Компанія',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Налаштування моделі постачальника.

        Унікальність назви постачальника в межах компанії запобігає
        дублюванню контрагентів у системі закупівель.
        """
        verbose_name = 'Постачальник'
        verbose_name_plural = 'Постачальники'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'company'],
                name='unique_supplier_name_per_company',
            ),
        ]

    def __str__(self) -> str:
        """Повертає назву постачальника з компанією."""
        return f'{self.name} — {self.company.name}'
