"""Сервісний шар для бізнес-логіки роботи із запчастинами та складом.

Ізолює логіку обліку складських залишків, резервування та списання
запчастин від представлень.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import F

from parts.models import Part


class PartService:
    """Сервіс для операцій зі складським обліком запчастин.

    Забезпечує атомарність операцій зміни залишків та захист
    від станів перегону (race conditions) через `F()` вирази.
    """

    @staticmethod
    @transaction.atomic
    def increase_stock(part: Part, quantity: Decimal) -> Part:
        """Збільшує залишок запчастини на складі.

        Використовується при оприбуткуванні товару за замовленням
        закупівлі або при поверненні зі складу.

        Args:
            part: Запчастина, залишок якої потрібно збільшити.
            quantity: Кількість для додавання (має бути > 0).

        Returns:
            Оновлений екземпляр Part з актуальним залишком.

        Raises:
            ValueError: Якщо quantity <= 0.
        """
        if quantity <= 0:
            raise ValueError('Кількість для додавання має бути більше 0.')

        Part.objects.filter(pk=part.pk).update(
            quantity_on_hand=F('quantity_on_hand') + quantity,
        )
        part.refresh_from_db()
        return part

    @staticmethod
    @transaction.atomic
    def decrease_stock(part: Part, quantity: Decimal) -> Part:
        """Зменшує залишок запчастини на складі (списання/продаж).

        Використовується при додаванні запчастини до заказ-наряду
        або при інвентаризаційному списанні.

        Args:
            part: Запчастина, залишок якої потрібно зменшити.
            quantity: Кількість для списання (має бути > 0).

        Returns:
            Оновлений екземпляр Part з актуальним залишком.

        Raises:
            ValueError: Якщо quantity <= 0 або недостатньо залишку.
        """
        if quantity <= 0:
            raise ValueError('Кількість для списання має бути більше 0.')

        # Атомарна перевірка та зменшення залишку
        updated: int = Part.objects.filter(
            pk=part.pk,
            quantity_on_hand__gte=quantity,
        ).update(
            quantity_on_hand=F('quantity_on_hand') - quantity,
        )

        if updated == 0:
            raise ValueError(
                f'Недостатньо залишку запчастини «{part.name}» '
                f'(арт. {part.part_number or "—"}) на складі. '
                f'Доступно: {part.quantity_on_hand}, потрібно: {quantity}.',
            )

        part.refresh_from_db()
        return part


