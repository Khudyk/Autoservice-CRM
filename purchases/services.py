"""Сервісний шар для бізнес-логіки закупівлі запчастин.

Ізолює складну логіку оприбуткування товару та оновлення складських
залишків від представлень. Гарантує атомарність та захист від станів
перегону (race conditions).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum, DecimalField, Value
from django.db.models.functions import Coalesce

from parts.models import PartLot
from purchases.models import PurchaseOrder, PurchaseOrderItem
from suppliers.models import Supplier


class PurchaseOrderService:
    """Сервіс для роботи із замовленнями закупівлі.

    Інкапсулює бізнес-логіку переходу між статусами, оприбуткування
    товару та оновлення складських залишків.
    """

    @staticmethod
    @transaction.atomic
    def receive_items(
        purchase: PurchaseOrder,
        receive_data: list[tuple[PurchaseOrderItem, Decimal]],
    ) -> PurchaseOrder:
        """Оприбутковує товар за замовленням з атомарним оновленням складу.

        Для кожної позиції:
        1. Атомарно збільшує `quantity_received` через `F()` вирази.
        2. Атомарно збільшує `Part.quantity_on_hand` через `F()` вирази.
        3. Визначає, чи всі позиції отримані повністю.

        Args:
            purchase: Замовлення закупівлі, за яким приймається товар.
            receive_data: Список кортежів (позиція, кількість_до_отримання).

        Returns:
            Оновлене замовлення з актуальним статусом.

        Raises:
            ValueError: Якщо кількість до отримання перевищує залишок.
        """
        all_fully_received: bool = True

        for item, qty in receive_data:
            if qty <= 0:
                continue

            # Атомарне оновлення отриманої кількості в позиції замовлення
            updated = PurchaseOrderItem.objects.filter(
                pk=item.pk,
                quantity_received__lte=F('quantity_ordered') - qty,
            ).update(quantity_received=F('quantity_received') + qty)
            if updated == 0:
                raise ValueError(
                    f'Кількість отримання ({qty}) перевищує залишок для позиції '
                    f'"{item.part.name}".'
                )

            # Атомарне оновлення залишку на складі запчастини
            from parts.models import Part

            Part.objects.filter(pk=item.part_id).update(
                quantity_on_hand=F('quantity_on_hand') + qty,
            )

            # Створюємо запис партії (PartLot) для кожної отриманої кількості
            PartLot.objects.create(
                purchase_item=item,
                part_id=item.part_id,
                quantity=qty,
                purchase_price=item.unit_price,
                company_id=item.purchase_order.company_id,
            )

            # Перевірка, чи позицію отримано повністю
            item.refresh_from_db()
            if item.quantity_received < item.quantity_ordered:
                all_fully_received = False

        # Оновлення статусу замовлення
        purchase.status = (
            PurchaseOrder.Status.RECEIVED
            if all_fully_received
            else PurchaseOrder.Status.PARTIALLY_RECEIVED
        )
        purchase.save(update_fields=['status'])

        return purchase

    @staticmethod
    @transaction.atomic
    def submit_order(purchase: PurchaseOrder) -> PurchaseOrder:
        """Переводить замовлення з чернетки в статус 'Замовлено'.

        Args:
            purchase: Замовлення в статусі DRAFT.

        Returns:
            Оновлене замовлення зі статусом ORDERED.

        Raises:
            ValueError: Якщо замовлення не в статусі DRAFT або не має позицій.
        """
        if purchase.status != PurchaseOrder.Status.DRAFT:
            raise ValueError(
                'Можна відправити лише замовлення в статусі «Чернетка».',
            )
        if not purchase.items.exists():
            raise ValueError('Не можна відправити замовлення без позицій.')

        purchase.status = PurchaseOrder.Status.ORDERED
        purchase.save(update_fields=['status'])
        return purchase

    @staticmethod
    @transaction.atomic
    def cancel_order(purchase: PurchaseOrder) -> PurchaseOrder:
        """Скасовує замовлення, якщо це дозволено за статусом.

        Args:
            purchase: Замовлення для скасування.

        Returns:
            Оновлене замовлення зі статусом CANCELLED.

        Raises:
            ValueError: Якщо замовлення вже отримано або скасовано.
        """
        if purchase.status in (
            PurchaseOrder.Status.RECEIVED,
            PurchaseOrder.Status.CANCELLED,
        ):
            raise ValueError(
                'Не можна скасувати замовлення в статусі '
                f'«{purchase.get_status_display()}».',
            )
        purchase.status = PurchaseOrder.Status.CANCELLED
        purchase.save(update_fields=['status'])
        return purchase


class SupplierPaymentService:
    """Сервіс для роботи з платежами постачальникам.

    Надає методи для розрахунку заборгованості та аналітики
    взаєморозрахунків із постачальниками.
    """

    @staticmethod
    def get_supplier_balance(supplier: Supplier) -> Decimal:
        """Розраховує поточний баланс (заборгованість) постачальнику.

        Баланс = сума отриманих товарів - сума сплачених платежів.
        Якщо баланс > 0 — компанія заборгувала постачальнику.
        Якщо баланс < 0 — постачальник має переплату (аванс).

        Args:
            supplier: Постачальник, для якого розраховується баланс.

        Returns:
            Decimal: Поточний баланс (додатне — борг, від'ємне — переплата).
        """
        # Сума вартості отриманих товарів
        received_total: Decimal = (
            PurchaseOrderItem.objects
            .filter(
                purchase_order__supplier=supplier,
                quantity_received__gt=0,
            )
            .aggregate(
                total=Coalesce(
                    Sum(F('quantity_received') * F('unit_price')),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(),
                ),
            )['total']
        )

        # Сума сплачених платежів (тільки проведені)
        paid_total: Decimal = (
            SupplierPayment.objects
            .filter(supplier=supplier, status='completed')
            .aggregate(
                total=Coalesce(
                    Sum('amount'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(),
                ),
            )['total']
        )

        return received_total - paid_total

    @staticmethod
    def get_supplier_purchases_total(
        supplier: Supplier,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> Decimal:
        """Розраховує загальну вартість отриманих товарів від постачальника.

        Args:
            supplier: Постачальник.
            date_from: Початкова дата (необов'язково).
            date_to: Кінцева дата (необов'язково).

        Returns:
            Decimal: Загальна вартість отриманих товарів.
        """
        qs = PurchaseOrderItem.objects.filter(
            purchase_order__supplier=supplier,
            quantity_received__gt=0,
        )
        if date_from:
            qs = qs.filter(
                purchase_order__created_at__date__gte=date_from,
            )
        if date_to:
            qs = qs.filter(
                purchase_order__created_at__date__lte=date_to,
            )
        result: Decimal = qs.aggregate(
            total=Coalesce(
                Sum(F('quantity_received') * F('unit_price')),
                Value(Decimal('0.00')),
                output_field=DecimalField(),
            ),
        )['total']
        return result

    @staticmethod
    def get_supplier_payments_total(
        supplier: Supplier,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> Decimal:
        """Розраховує загальну суму платежів постачальнику.

        Args:
            supplier: Постачальник.
            date_from: Початкова дата (необов'язково).
            date_to: Кінцева дата (необов'язково).

        Returns:
            Decimal: Загальна сума платежів.
        """
        qs = SupplierPayment.objects.filter(
            supplier=supplier, status='completed',
        )
        if date_from:
            qs = qs.filter(payment_date__gte=date_from)
        if date_to:
            qs = qs.filter(payment_date__lte=date_to)
        result: Decimal = qs.aggregate(
            total=Coalesce(
                Sum('amount'),
                Value(Decimal('0.00')),
                output_field=DecimalField(),
            ),
        )['total']
        return result
