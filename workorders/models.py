"""Моделі для заказ-нарядів автосервісу.

Включає:
- WorkOrder — основний заказ-наряд
- WorkOrderService — рядки робіт/послуг
- WorkOrderPart — рядки запчастин
"""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum, F, ExpressionWrapper, DecimalField


class WorkOrder(models.Model):
    """Заказ-наряд на виконання робіт з ремонту/обслуговування автомобіля."""

    class Status(models.TextChoices):
        """Статуси життєвого циклу наряду."""
        DRAFT = 'draft', 'Чернетка'
        IN_PROGRESS = 'in_progress', 'В роботі'
        COMPLETED = 'completed', 'Завершено'
        AWAITING_PAYMENT = 'awaiting_payment', 'Очікує оплати'
        CANCELLED = 'cancelled', 'Скасовано'

    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='work_orders',
        verbose_name='Компанія',
    )
    vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        on_delete=models.CASCADE,
        related_name='work_orders',
        verbose_name='Автомобіль',
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='work_orders',
        verbose_name='Клієнт',
        help_text='Клієнт за нарядом (може відрізнятися від власника авто)',
    )
    created_by = models.ForeignKey(
        'accounts.Employee',
        on_delete=models.CASCADE,
        related_name='work_orders',
        verbose_name='Створив',
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name='Статус',
    )
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name='Нотатки',
    )
    mileage = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name='Пробіг, км',
        help_text='Пробіг автомобіля на момент створення наряду',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Створено',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Оновлено',
    )

    class Meta:
        """Налаштування моделі заказ-наряду.

        Сортування від найновіших до найстаріших — за замовчуванням
        користувач бачить останні створені наряди першими.
        """
        ordering = ['-created_at']
        verbose_name = 'Заказ-наряд'
        verbose_name_plural = 'Заказ-наряди'

    def __str__(self) -> str:
        """Повертає рядкове представлення: номер наряду та автомобіль."""
        return f'Наряд #{self.pk} — {self.vehicle}'

    @property
    def total_labor_cost(self) -> Decimal:
        """Вартість усіх робіт у наряді."""
        total = self.services.aggregate(
            total=ExpressionWrapper(
                Sum(F('quantity') * F('unit_price')),
                output_field=DecimalField(),
            ),
        )['total']
        return total or Decimal('0.00')

    @property
    def total_parts_cost(self) -> Decimal:
        """Вартість усіх запчастин у наряді."""
        total = self.parts.aggregate(
            total=ExpressionWrapper(
                Sum(F('quantity') * F('unit_price')),
                output_field=DecimalField(),
            ),
        )['total']
        return total or Decimal('0.00')

    @property
    def total_amount(self) -> Decimal:
        """Загальна вартість наряду (роботи + запчастини)."""
        return self.total_labor_cost + self.total_parts_cost

    @property
    def is_editable(self) -> bool:
        """Чи можна редагувати наряд.

        Редагування дозволено для всіх статусів, крім завершеного
        та скасованого — ці статуси є термінальними.
        """
        return self.status not in (
            self.Status.COMPLETED,
            self.Status.CANCELLED,
        )



class WorkOrderService(models.Model):
    """Рядок роботи/послуги в заказ-наряді.

    Кожен рядок представляє один вид роботи (наприклад, "Заміна масла"),
    виконаний певним співробітником.
    """

    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name='services',
        verbose_name='Заказ-наряд',
    )
    work_type = models.ForeignKey(
        'worktypes.WorkType',
        on_delete=models.PROTECT,
        related_name='work_order_services',
        verbose_name='Вид роботи',
    )
    quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Кількість (нормо-годин)',
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Ціна за од., грн',
    )
    employee = models.ForeignKey(
        'accounts.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_services',
        verbose_name='Виконавець',
    )
    description = models.CharField(
        max_length=500,
        blank=True,
        default='',
        verbose_name='Опис',
    )

    class Meta:
        """Налаштування моделі роботи в наряді."""
        verbose_name = 'Робота в наряді'
        verbose_name_plural = 'Роботи в наряді'

    def __str__(self) -> str:
        """Повертає назву роботи та кількість нормо-годин."""
        return f'{self.work_type.name} — {self.quantity} год'

    @property
    def total(self) -> Decimal:
        """Вартість рядка: кількість × ціна."""
        return self.quantity * self.unit_price


class WorkOrderPart(models.Model):
    """Рядок запчастини в заказ-наряді.

    Фіксує використану запчастину, її кількість та ціну продажу
    на момент оформлення наряду.
    """

    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name='parts',
        verbose_name='Заказ-наряд',
    )
    part = models.ForeignKey(
        'parts.Part',
        on_delete=models.PROTECT,
        related_name='work_order_parts',
        verbose_name='Запчастина',
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Кількість',
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Ціна за од., грн',
    )
    part_lot = models.ForeignKey(
        'parts.PartLot',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='work_order_parts',
        verbose_name='Партія закупівлі',
        help_text='Партія запчастин, з якої взято цю одиницю. Потрібна для розрахунку прибутку.',
    )
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Закупівельна ціна за од., грн',
        help_text='Ціна закупівлі на момент створення рядка (копія з PartLot)',
    )

    class Meta:
        """Налаштування моделі запчастини в наряді."""
        verbose_name = 'Запчастина в наряді'
        verbose_name_plural = 'Запчастини в наряді'

    def __str__(self) -> str:
        """Повертає назву запчастини та кількість."""
        return f'{self.part.name} × {self.quantity}'

    @property
    def total(self) -> Decimal:
        """Вартість рядка: кількість × ціна."""
        return self.quantity * self.unit_price

    @property
    def total_purchase_cost(self) -> Decimal:
        """Загальна закупівельна вартість рядка.

        Returns:
            Decimal: quantity * purchase_price, або 0, якщо ціна не вказана.
        """
        if self.purchase_price is None:
            return Decimal('0.00')
        return self.quantity * self.purchase_price

    @property
    def profit(self) -> Decimal:
        """Прибуток від продажу цієї запчастини в наряді.

        Returns:
            Decimal: (unit_price - purchase_price) * quantity.
        """
        return self.total - self.total_purchase_cost
