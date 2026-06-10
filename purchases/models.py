"""Моделі додатку purchases — закупівля запчастин та матеріалів."""

from __future__ import annotations

from decimal import Decimal

from django.db import models


class PurchaseOrder(models.Model):
    """Модель замовлення постачальнику на закупівлю запчастин.

    Кожне замовлення прив'язане до компанії (data isolation).
    Містить перелік позицій (PurchaseOrderItem) з кількостями та цінами.
    При отриманні товару оновлюється залишок на складі (Part.quantity_on_hand).
    """

    class Status(models.TextChoices):
        """Статуси замовлення закупівлі."""
        DRAFT = 'draft', 'Чернетка'
        ORDERED = 'ordered', 'Замовлено'
        PARTIALLY_RECEIVED = 'partially_received', 'Частково отримано'
        RECEIVED = 'received', 'Отримано'
        CANCELLED = 'cancelled', 'Скасовано'

    order_number = models.CharField(
        'Номер замовлення',
        max_length=50,
        help_text='Автоматично згенерований номер замовлення',
    )
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.CASCADE,
        related_name='purchase_orders',
        verbose_name='Постачальник',
    )
    status = models.CharField(
        'Статус',
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField(
        'Нотатки',
        blank=True,
        help_text='Додаткова інформація про замовлення',
    )
    created_by = models.ForeignKey(
        'accounts.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_orders',
        verbose_name='Створив',
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='purchase_orders',
        verbose_name='Компанія',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Налаштування моделі замовлення закупівлі.

        Унікальність номера замовлення в межах компанії гарантує
        однозначну ідентифікацію при спілкуванні з постачальниками.
        """
        verbose_name = 'Замовлення закупівлі'
        verbose_name_plural = 'Замовлення закупівлі'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['order_number', 'company'],
                name='unique_order_number_per_company',
            ),
        ]

    def __str__(self) -> str:
        """Повертає номер та постачальника замовлення."""
        return f'{self.order_number} — {self.supplier.name}'

    @property
    def total_amount(self) -> Decimal:
        """Загальна сума замовлення (сума всіх позицій) через агрегацію.

        Використовує `annotate` з `Sum` та `F()` для обчислення на рівні БД,
        що уникає проблеми N+1 запитів.
        """
        from django.db.models import Sum, F, DecimalField, Value
        from django.db.models.functions import Coalesce

        result: Decimal = self.items.aggregate(
            total=Coalesce(
                Sum(F('quantity_ordered') * F('unit_price')),
                Value(Decimal('0.00')),
                output_field=DecimalField(),
            ),
        )['total']
        return result

    @property
    def is_editable(self) -> bool:
        """Чи можна редагувати замовлення (тільки чернетка)."""
        return self.status == self.Status.DRAFT

    @property
    def is_receivable(self) -> bool:
        """Чи можна приймати товар за цим замовленням."""
        return self.status in (
            self.Status.ORDERED,
            self.Status.PARTIALLY_RECEIVED,
        )

    @classmethod
    def generate_order_number(cls, company_id: int) -> str:
        """Генерує наступний номер замовлення для компанії.

        Формат: PO-XXXXX (де XXXXX — порядковий номер з ведучими нулями).

        Args:
            company_id: ID компанії.

        Returns:
            Новий номер замовлення.
        """
        last_order: PurchaseOrder | None = cls.objects.filter(
            company_id=company_id,
        ).order_by('id').last()
        if last_order and last_order.order_number.startswith('PO-'):
            try:
                last_num: int = int(last_order.order_number.split('-')[1])
                next_num: int = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        return f'PO-{next_num:05d}'


class PurchaseOrderItem(models.Model):
    """Позиція замовлення закупівлі — конкретна запчастина з кількістю та ціною.

    Кількість отриманого (quantity_received) оновлюється при оприбуткуванні,
    що також збільшує Part.quantity_on_hand.
    """

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Замовлення',
    )
    part = models.ForeignKey(
        'parts.Part',
        on_delete=models.PROTECT,
        related_name='purchase_items',
        verbose_name='Запчастина',
        help_text='Запчастина, яку неможливо видалити, якщо вона є в прихідних накладних',
    )
    quantity_ordered = models.DecimalField(
        'Замовлено',
        max_digits=10,
        decimal_places=2,
        help_text='Кількість замовлених одиниць',
    )
    quantity_received = models.DecimalField(
        'Отримано',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Кількість фактично отриманих одиниць',
    )
    unit_price = models.DecimalField(
        'Ціна за одиницю, грн',
        max_digits=10,
        decimal_places=2,
        help_text='Закупівельна ціна за одиницю',
    )

    class Meta:
        """Налаштування моделі позиції замовлення.

        Сортування за ID гарантує стабільний порядок рядків
        у межах одного замовлення.
        """
        verbose_name = 'Позиція замовлення'
        verbose_name_plural = 'Позиції замовлення'
        ordering = ['id']

    def __str__(self) -> str:
        """Повертає назву запчастини та кількість."""
        return f'{self.part.name} — {self.quantity_ordered} x {self.unit_price} грн'

    @property
    def total_price(self) -> Decimal:
        """Вартість позиції (замовлена кількість * ціна)."""
        return self.quantity_ordered * self.unit_price

    @property
    def remaining_to_receive(self) -> Decimal:
        """Скільки ще залишилося отримати."""
        return self.quantity_ordered - self.quantity_received



class SupplierPayment(models.Model):
    """Платіж постачальнику за придбані запчастини.

    Фіксує факт оплати постачальнику, що дозволяє відстежувати
    взаєморозрахунки: скільки заборговано та скільки сплачено.
    Кожен платіж має унікальний номер формату PAY-XXXXX.
    """

    class Status(models.TextChoices):
        """Статуси платежу постачальнику."""
        PENDING = 'pending', 'Очікується'
        COMPLETED = 'completed', 'Проведено'
        CANCELLED = 'cancelled', 'Скасовано'

    class PaymentType(models.TextChoices):
        """Способи оплати постачальникам."""
        CASH = 'cash', 'Готівка'
        BANK_TRANSFER = 'bank_transfer', 'Банківський переказ'
        CARD = 'card', 'Картка'
        OTHER = 'other', 'Інше'

    payment_number = models.CharField(
        'Номер платежу',
        max_length=50,
        blank=True,
        help_text='Автоматично згенерований номер платежу',
    )
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Постачальник',
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='supplier_payments',
        verbose_name='Компанія',
    )
    amount = models.DecimalField(
        'Сума, грн',
        max_digits=12,
        decimal_places=2,
        help_text='Сума платежу в гривнях',
    )
    payment_date = models.DateField(
        'Дата оплати',
        db_index=True,
    )
    payment_type = models.CharField(
        'Спосіб оплати',
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.BANK_TRANSFER,
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name='Замовлення',
        help_text='Замовлення, за яке здійснюється оплата (необов\'язково)',
    )
    notes = models.TextField(
        'Нотатки',
        blank=True,
        help_text='Призначення платежу, номер рахунку тощо',
    )
    created_by = models.ForeignKey(
        'accounts.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_payments',
        verbose_name='Створив',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Налаштування моделі платежу постачальнику.

        Унікальність номера платежу в межах компанії забезпечує
        прозорість фінансового обліку. Індекси пришвидшують
        фільтрацію за постачальником та датою.
        """
        verbose_name = 'Платіж постачальнику'
        verbose_name_plural = 'Платежі постачальникам'
        ordering = ['-payment_date', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['payment_number', 'company'],
                name='unique_payment_number_per_company',
            ),
        ]
        indexes = [
            models.Index(fields=['supplier', 'payment_date']),
            models.Index(fields=['company', 'payment_date']),
        ]

    def __str__(self) -> str:
        """Повертає опис платежу."""
        number: str = self.payment_number or f'#{self.pk}'
        return (
            f'{number} — {self.supplier.name} — {self.amount} грн '
            f'({self.payment_date})'
        )

    @classmethod
    def generate_payment_number(cls, company_id: int) -> str:
        """Генерує наступний номер платежу для компанії.

        Формат: PAY-XXXXX (де XXXXX — порядковий номер з ведучими нулями).

        Args:
            company_id: ID компанії.

        Returns:
            Новий номер платежу.
        """
        last_payment: SupplierPayment | None = cls.objects.filter(
            company_id=company_id,
        ).order_by('id').last()
        if last_payment and last_payment.payment_number.startswith('PAY-'):
            try:
                last_num: int = int(last_payment.payment_number.split('-')[1])
                next_num: int = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        return f'PAY-{next_num:05d}'
