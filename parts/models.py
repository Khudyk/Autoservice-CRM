"""Моделі додатку parts — облік запчастин та складських запасів."""

from __future__ import annotations

from decimal import Decimal

from django.db import models


class Part(models.Model):
    """Модель запчастини/матеріалу для автомобілів.

    Кожна запчастина прив'язана до компанії (data isolation).
    Ведеться складський облік: кількість, мінімальний залишок,
    закупівельна та продажна ціна.
    """

    class Unit(models.TextChoices):
        """Одиниці виміру запчастин та матеріалів."""
        PIECE = 'pc', 'шт'
        LITER = 'l', 'л'
        KILOGRAM = 'kg', 'кг'
        METER = 'm', 'м'
        SET = 'set', 'комплект'
        PACK = 'pack', 'упаковка'
        OTHER = 'other', 'інше'

    name = models.CharField(
        'Назва запчастини',
        max_length=255,
        db_index=True,
    )
    part_number = models.CharField(
        'Артикул',
        max_length=100,
        blank=True,
        help_text='Оригінальний номер запчастини/OEM-номер',
    )
    manufacturer = models.CharField(
        'Виробник',
        max_length=255,
        blank=True,
        help_text='Назва виробника запчастини',
    )
    unit = models.CharField(
        'Одиниця виміру',
        max_length=10,
        choices=Unit.choices,
        default=Unit.PIECE,
    )
    selling_price = models.DecimalField(
        'Ціна продажу, грн',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    min_quantity = models.DecimalField(
        'Мінімальний залишок',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='При досягненні цієї кількості бажано замовити додатково',
    )
    location = models.CharField(
        'Місце на складі',
        max_length=100,
        blank=True,
        help_text='Стелаж/полиця/комірка',
    )
    quantity_on_hand = models.DecimalField(
        'Залишок на складі',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Поточна кількість на складі. Оновлюється автоматично при оприбуткуванні закупівель.',
    )
    is_active = models.BooleanField(
        'Активна',
        default=True,
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='parts',
        verbose_name='Компанія',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Налаштування моделі запчастини.

        Унікальність артикула в межах компанії запобігає дублюванню
        номенклатури на складі.
        """
        verbose_name = 'Запчастина'
        verbose_name_plural = 'Запчастини'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['part_number', 'company'],
                name='unique_part_number_per_company',
            ),
        ]

    @property
    def has_purchase_orders(self) -> bool:
        """Перевіряє, чи є прихідні накладні, що містять цю запчастину.

        Returns:
            True, якщо існує хоча б одна позиція прихідної накладної
            (PurchaseOrderItem), що посилається на цю запчастину.
        """
        return self.purchase_items.exists()

    def __str__(self) -> str:
        """Повертає назву запчастини з артикулом та компанією."""
        if self.part_number:
            return f'{self.name} ({self.part_number}) — {self.company.name}'
        return f'{self.name} — {self.company.name}'


class PartLot(models.Model):
    """Партія запчастин, отримана за конкретною закупівлею.

    Створюється автоматично при оприбуткуванні товару за замовленням
    закупівлі (PurchaseOrder). Кожна партія прив'язана до однієї позиції
    замовлення (PurchaseOrderItem) і відстежує, скільки одиниць з цієї
    партії вже використано в заказ-нарядах.

    Дозволяє розрахувати прибуток від продажу запчастин:
    прибуток = (ціна_продажу - закупівельна_ціна) * кількість.

    Обмеження: кількість використаних одиниць не може перевищувати
    кількість, отриману в партії (quantity - quantity_used >= 0).
    """

    purchase_item = models.ForeignKey(
        'purchases.PurchaseOrderItem',
        on_delete=models.CASCADE,
        related_name='lots',
        verbose_name='Позиція закупівлі',
    )
    part = models.ForeignKey(
        Part,
        on_delete=models.CASCADE,
        related_name='lots',
        verbose_name='Запчастина',
    )
    quantity = models.DecimalField(
        'Кількість в партії',
        max_digits=10,
        decimal_places=2,
        help_text='Кількість, отримана за цією закупівлею',
    )
    quantity_used = models.DecimalField(
        'Використано',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Скільки одиниць з цієї партії вже використано в нарядах',
    )
    purchase_price = models.DecimalField(
        'Закупівельна ціна за од., грн',
        max_digits=10,
        decimal_places=2,
        help_text='Ціна, за якою було придбано запчастину',
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='part_lots',
        verbose_name='Компанія',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата оприбуткування',
    )

    class Meta:
        """Налаштування моделі партії запчастин.

        Індекс за складом (part, company) пришвидшує пошук партій
        при створенні заказ-нарядів.
        """
        verbose_name = 'Партія запчастин'
        verbose_name_plural = 'Партії запчастин'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['part', 'company']),
        ]

    def __str__(self) -> str:
        """Повертає назву партії з кількістю та замовленням."""
        return (
            f'{self.part.name} — {self.purchase_item.purchase_order.order_number} '
            f'(доступно: {self.quantity_available} {self.part.get_unit_display()})'
        )

    @property
    def quantity_available(self) -> Decimal:
        """Доступна кількість для використання в нарядах.

        Returns:
            Decimal: quantity - quantity_used.
        """
        return self.quantity - self.quantity_used
