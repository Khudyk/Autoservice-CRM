"""Моделі додатку worktypes — перелік видів робіт автосервісу."""

from __future__ import annotations

from django.db import models


class WorkType(models.Model):
    """Модель виду роботи/послуги, яку надає автосервіс.

    Кожен вид роботи прив'язаний до компанії (data isolation).
    """

    class Category(models.TextChoices):
        """Категорії робіт."""
        REPAIR = 'repair', 'Ремонт'
        MAINTENANCE = 'maintenance', 'ТО'
        DIAGNOSTICS = 'diagnostics', 'Діагностика'
        ELECTRICAL = 'electrical', 'Електрика'
        BODYWORK = 'bodywork', 'Кузовні роботи'
        TYRE = 'tyre', 'Шиномонтаж'
        DETAILING = 'detailing', 'Детейлінг'
        OTHER = 'other', 'Інше'

    name = models.CharField(
        'Назва роботи',
        max_length=255,
        db_index=True,
    )
    description = models.TextField(
        'Опис',
        blank=True,
        help_text='Детальний опис роботи',
    )
    category = models.CharField(
        'Категорія',
        max_length=30,
        choices=Category.choices,
        default=Category.OTHER,
    )
    is_active = models.BooleanField(
        'Активна',
        default=True,
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='worktypes',
        verbose_name='Компанія',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Налаштування моделі виду робіт.

        Унікальність назви роботи в межах компанії запобігає дублюванню
        видів послуг у довіднику.
        """
        verbose_name = 'Вид роботи'
        verbose_name_plural = 'Види робіт'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'company'],
                name='unique_worktype_name_per_company',
            ),
        ]

    def __str__(self) -> str:
        """Повертає назву роботи з компанією."""
        return f'{self.name} — {self.company.name}'
