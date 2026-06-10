"""Модель компанії (мульти-тенантне ядро).

Кожен запис у системі належить певній компанії через зовнішній ключ `company`.
Це забезпечує ізоляцію даних між різними СТО (автосервісами), які
використовують одну інсталяцію системи.
"""

from django.db import models


class Company(models.Model):
    """Модель компанії-клієнта (автосервісу).

    Є кореневою сутністю мульти-тенантної архітектури. Кожен окремий
    автосервіс реєструється як окрема компанія, і всі дані (автомобілі,
    співробітники, замовлення, запчастини, наряди) прив'язуються до неї.
    """

    name = models.CharField("Назва", max_length=255)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    address = models.TextField("Адреса", blank=True)
    notes = models.TextField("Нотатки", blank=True)
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Створено',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Оновлено',
    )

    class Meta:
        verbose_name = "Компанія"
        verbose_name_plural = "Компанії"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Повертає назву компанії для відображення в інтерфейсі."""
        return self.name
