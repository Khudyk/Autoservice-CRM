"""Сервісний шар для роботи із заказ-нарядами.

Містить бізнес-логіку створення, оновлення та обчислення
заказ-нарядів та їхніх рядків (роботи, запчастини).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import F, Prefetch, QuerySet
from django.forms import BaseFormSet

from parts.models import Part, PartLot
from parts.services import PartService
from workorders.models import WorkOrder, WorkOrderPart, WorkOrderService


class WorkOrderServiceError(Exception):
    """Базове виключення для помилок сервісу заказ-нарядів."""


class WorkOrderServiceLogic:
    """Сервіс для роботи з бізнес-логікою заказ-нарядів.

    Інкапсулює створення/оновлення наряду разом з його рядками
    в атомарних транзакціях.
    """

    @staticmethod
    @transaction.atomic
    def create_work_order_with_items(
        work_order: WorkOrder,
        service_formset: BaseFormSet,
        part_formset: BaseFormSet,
    ) -> WorkOrder:
        """Створює заказ-наряд разом з рядками робіт та запчастин.

        Args:
            work_order: Незбережений екземпляр WorkOrder.
            service_formset: Набір форм для WorkOrderService (вже валідований).
            part_formset: Набір форм для WorkOrderPart (вже валідований).

        Returns:
            Збережений екземпляр WorkOrder.

        Raises:
            WorkOrderServiceError: Якщо недостатньо залишку в партії
                (race condition між валідацією форми та збереженням).
        """
        work_order.save()

        # Зберігаємо рядки робіт
        service_instances = service_formset.save(commit=False)
        for instance in service_instances:
            instance.work_order = work_order
            instance.save()
        for deleted in service_formset.deleted_objects:
            deleted.delete()

        # Зберігаємо рядки запчастин
        part_instances = part_formset.save(commit=False)
        for instance in part_instances:
            instance.work_order = work_order

            # Якщо вибрано партію — копіюємо закупівельну ціну
            if instance.part_lot_id and instance.purchase_price is None:
                instance.purchase_price = instance.part_lot.purchase_price

            instance.save()

            # Списуємо зі складу
            if instance.pk:
                PartService.decrease_stock(
                    part=instance.part,
                    quantity=instance.quantity,
                )

            # Збільшуємо лічильник використаних у партії
            # Атомарна перевірка: quantity_used + quantity <= quantity
            if instance.part_lot_id:
                updated: int = PartLot.objects.filter(
                    pk=instance.part_lot_id,
                    quantity__gte=F('quantity_used') + instance.quantity,
                ).update(
                    quantity_used=F('quantity_used') + instance.quantity,
                )
                if updated == 0:
                    raise WorkOrderServiceError(
                        f'Недостатньо залишку в партії {instance.part_lot} '
                        f'для запчастини "{instance.part.name}". '
                        f'Запитано: {instance.quantity}, але доступний залишок '
                        f'менший за необхідний.',
                    )

        for deleted in part_formset.deleted_objects:
            # Повертаємо на склад
            if isinstance(deleted, WorkOrderPart) and deleted.pk:
                PartService.increase_stock(
                    part=deleted.part,
                    quantity=deleted.quantity,
                )
                # Зменшуємо лічильник використаних у партії
                if deleted.part_lot_id:
                    PartLot.objects.filter(pk=deleted.part_lot_id).update(
                        quantity_used=F('quantity_used') - deleted.quantity,
                    )
            deleted.delete()

        return work_order

    @staticmethod
    @transaction.atomic
    def update_work_order_with_items(
        work_order: WorkOrder,
        service_formset: BaseFormSet,
        part_formset: BaseFormSet,
    ) -> WorkOrder:
        """Оновлює заказ-наряд та його рядки.

        При зміні рядків запчастин корегує залишки на складі:
        - видалені рядки повертають запчастини на склад;
        - нові рядки списують зі складу;
        - змінені кількості коригуються.

        Args:
            work_order: Існуючий (збережений) екземпляр WorkOrder.
            service_formset: Набір форм для WorkOrderService (вже валідований).
            part_formset: Набір форм для WorkOrderPart (вже валідований).

        Returns:
            Оновлений екземпляр WorkOrder.

        Raises:
            WorkOrderServiceError: Якщо недостатньо залишку в партії
                (race condition між валідацією форми та збереженням).
        """
        work_order.save()

        # Обробка рядків робіт
        saved_services = service_formset.save(commit=False)
        for instance in saved_services:
            instance.work_order = work_order
            instance.save()
        for deleted in service_formset.deleted_objects:
            deleted.delete()

        # Обробка рядків запчастин
        saved_parts = part_formset.save(commit=False)

        # Спочатку видалені — повертаємо на склад
        for deleted in part_formset.deleted_objects:
            if isinstance(deleted, WorkOrderPart) and deleted.pk:
                PartService.increase_stock(
                    part=deleted.part,
                    quantity=deleted.quantity,
                )
                # Зменшуємо лічильник використаних у партії
                if deleted.part_lot_id:
                    PartLot.objects.filter(pk=deleted.part_lot_id).update(
                        quantity_used=F('quantity_used') - deleted.quantity,
                    )
            deleted.delete()

        # Збережені (нові або змінені)
        for instance in saved_parts:
            instance.work_order = work_order

            # Копіюємо закупівельну ціну з партії, якщо вибрано нову партію
            if instance.part_lot_id and instance.purchase_price is None:
                instance.purchase_price = instance.part_lot.purchase_price

            # Обробка змін кількості та партії
            if instance.pk:
                old = WorkOrderPart.objects.get(pk=instance.pk)

                # Якщо змінилась партія — коригуємо обидві
                if instance.part_lot_id != old.part_lot_id:
                    # Звільняємо стару партію (зменшення — безпечно)
                    if old.part_lot_id:
                        PartLot.objects.filter(pk=old.part_lot_id).update(
                            quantity_used=F('quantity_used') - old.quantity,
                        )
                    # Займаємо нову партію — атомарна перевірка залишку
                    if instance.part_lot_id:
                        updated: int = PartLot.objects.filter(
                            pk=instance.part_lot_id,
                            quantity__gte=(
                                F('quantity_used') + instance.quantity
                            ),
                        ).update(
                            quantity_used=(
                                F('quantity_used') + instance.quantity
                            ),
                        )
                        if updated == 0:
                            raise WorkOrderServiceError(
                                f'Недостатньо залишку в партії '
                                f'{instance.part_lot} для запчастини '
                                f'"{instance.part.name}". '
                                f'Запитано: {instance.quantity}.',
                            )
                elif instance.part_lot_id and instance.quantity != old.quantity:
                    # Одна й та сама партія, змінилась кількість — коригуємо
                    diff: Decimal = instance.quantity - old.quantity
                    if diff > 0:
                        # Збільшення — атомарна перевірка залишку
                        updated: int = PartLot.objects.filter(
                            pk=instance.part_lot_id,
                            quantity__gte=(
                                F('quantity_used') + diff
                            ),
                        ).update(
                            quantity_used=F('quantity_used') + diff,
                        )
                        if updated == 0:
                            raise WorkOrderServiceError(
                                f'Недостатньо залишку в партії '
                                f'{instance.part_lot} для збільшення '
                                f'кількості запчастини '
                                f'"{instance.part.name}" на {diff}.',
                            )
                    else:
                        # Зменшення — безпечно
                        PartLot.objects.filter(
                            pk=instance.part_lot_id,
                        ).update(
                            quantity_used=F('quantity_used') + diff,
                        )

                # Коригуємо складський залишок
                diff: Decimal = instance.quantity - old.quantity
                if diff > 0:
                    PartService.decrease_stock(part=instance.part, quantity=diff)
                elif diff < 0:
                    PartService.increase_stock(part=instance.part, quantity=-diff)
            else:
                # Новий рядок
                PartService.decrease_stock(
                    part=instance.part,
                    quantity=instance.quantity,
                )
                if instance.part_lot_id:
                    # Атомарна перевірка залишку нової партії
                    updated: int = PartLot.objects.filter(
                        pk=instance.part_lot_id,
                        quantity__gte=(
                            F('quantity_used') + instance.quantity
                        ),
                    ).update(
                        quantity_used=(
                            F('quantity_used') + instance.quantity
                        ),
                    )
                    if updated == 0:
                        raise WorkOrderServiceError(
                            f'Недостатньо залишку в партії '
                            f'{instance.part_lot} для запчастини '
                            f'"{instance.part.name}". '
                            f'Запитано: {instance.quantity}.',
                        )
            instance.save()

        return work_order


    @staticmethod
    def calculate_work_order_total(work_order: WorkOrder) -> Decimal:
        """Обчислює загальну вартість заказ-наряду.

        Підсумовує всі рядки робіт та запчастин.

        Args:
            work_order: Екземпляр WorkOrder.

        Returns:
            Decimal: Загальна сума.
        """
        services_total: Decimal = sum(
            (s.quantity * s.unit_price for s in work_order.services.all()),
            Decimal('0.00'),
        )
        parts_total: Decimal = sum(
            (p.quantity * p.unit_price for p in work_order.parts.all()),
            Decimal('0.00'),
        )
        return services_total + parts_total
