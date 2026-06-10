"""Моделі додатку vehicles — облік автомобілів клієнтів СТО."""

from __future__ import annotations

from django.db import models


class Vehicle(models.Model):
    """Модель автомобіля з технічними характеристиками.

    Кожен автомобіль прив'язаний до компанії (data isolation).
    """

    class EngineType(models.TextChoices):
        """Типи двигунів."""
        PETROL = 'petrol', 'Бензин'
        DIESEL = 'diesel', 'Дизель'
        ELECTRIC = 'electric', 'Електрика'
        HYBRID = 'hybrid', 'Гібрид'
        GAS = 'gas', 'Газ'

    vin_code = models.CharField(
        'VIN-код',
        max_length=17,
        db_index=True,
        help_text='17 символів, унікальний в межах компанії',
    )
    brand = models.CharField(
        'Марка',
        max_length=100,
        db_index=True,
    )
    model = models.CharField(
        'Модель',
        max_length=100,
    )
    year = models.IntegerField(
        'Рік випуску',
    )
    engine_type = models.CharField(
        'Тип двигуна',
        max_length=20,
        choices=EngineType.choices,
        default=EngineType.PETROL,
    )
    engine_displacement = models.DecimalField(
        'Об\'єм двигуна, л',
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text='У літрах (напр. 2.0). Для електромобілів — порожньо',
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='vehicles',
        verbose_name='Компанія',
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vehicles',
        verbose_name='Власник',
        help_text='Клієнт-власник автомобіля (необов\'язково)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Налаштування моделі автомобіля.

        Унікальність VIN-коду в межах компанії запобігає дублюванню
        автомобілів.
        """
        verbose_name = 'Автомобіль'
        verbose_name_plural = 'Автомобілі'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['vin_code', 'company'],
                name='unique_vin_per_company',
            ),
        ]

    def __str__(self) -> str:
        """Повертає рядкове представлення: марка модель (VIN)."""
        return f'{self.brand} {self.model} ({self.vin_code})'
