"""Сервісний шар для роботи із заказ-нарядами.

Містить бізнес-логіку створення, оновлення та обчислення
заказ-нарядів та їхніх рядків (роботи, запчастини).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

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


# ---- Звіт по зарплаті механіків ----------------------------------------


@dataclass
class MechanicSummaryRow:
    """Підсумковий рядок звіту по зарплаті механіка.

    Атрибути:
        employee: Співробітник-механік.
        labor_percent: Відсоток від вартості робіт.
        services_count: Кількість виконаних робіт.
        total_service_cost: Загальна вартість виконаних робіт (грн).
        total_earnings: Загальне нарахування (грн).
    """
    employee: Any  # Employee
    labor_percent: Decimal
    services_count: int
    total_service_cost: Decimal
    total_earnings: Decimal


def get_all_mechanics_summary(
    company: Any,  # Company
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[MechanicSummaryRow]:
    """Повертає зведений звіт по зарплаті всіх механіків компанії.

    Для кожного співробітника з роллю 'mechanic' підраховує
    загальну вартість виконаних робіт та нарахування за формулою:
    `total_service_cost × labor_percent / 100`.

    Args:
        company: Компанія, для якої формується звіт.
        date_from: Початкова дата створення наряду (опціонально).
        date_to: Кінцева дата створення наряду (опціонально).

    Returns:
        Список MechanicSummaryRow, відсортований за нарахуванням (спадання).
    """
    from accounts.models import Employee

    # Отримуємо всіх співробітників з роллю 'mechanic'
    mechanics: list[Employee] = list(
        Employee.objects.filter(
            company=company,
            roles__codename='mechanic',
        ).select_related('user').prefetch_related('roles'),
    )

    rows: list[MechanicSummaryRow] = []
    for mechanic in mechanics:
        # Усі сервіси, виконані цим механіком
        svc_qs: QuerySet[WorkOrderService] = WorkOrderService.objects.filter(
            employee=mechanic,
        )

        # Фільтр за датою наряду
        if date_from is not None:
            svc_qs = svc_qs.filter(
                work_order__created_at__date__gte=date_from,
            )
        if date_to is not None:
            svc_qs = svc_qs.filter(
                work_order__created_at__date__lte=date_to,
            )

        # Агрегуємо через ORM — один запит на механіка
        from django.db.models import Sum, ExpressionWrapper, F, DecimalField

        aggregated = svc_qs.aggregate(
            total_cost=Sum(
                ExpressionWrapper(
                    F('quantity') * F('unit_price'),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                ),
            ),
            count=Sum(1),  # count via Sum(1) gives int
        )

        total_cost: Decimal = aggregated['total_cost'] or Decimal('0.00')
        cnt: int = aggregated['count'] or 0

        labor_pct: Decimal = mechanic.labor_percent or Decimal('0.00')
        earnings: Decimal = Decimal('0.00')
        if labor_pct > Decimal('0.00') and total_cost > Decimal('0.00'):
            earnings = (total_cost * labor_pct) / Decimal('100')
            earnings = earnings.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        rows.append(MechanicSummaryRow(
            employee=mechanic,
            labor_percent=labor_pct,
            services_count=cnt,
            total_service_cost=total_cost.quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP,
            ),
            total_earnings=earnings,
        ))

    rows.sort(key=lambda r: r.total_earnings, reverse=True)
    return rows


# ──────────────────────────────────────────────
# Звіт по зарплаті менеджерів
# ──────────────────────────────────────────────


@dataclass
class ManagerSummaryRow:
    """Рядок звіту по зарплаті менеджера.

    Атрибути:
        employee: Співробітник (менеджер).
        labor_percent: Відсоток від вартості робіт.
        parts_sale_percent: Відсоток від прибутку з запчастин.
        orders_count: Кількість створених нарядів.
        total_service_cost: Загальна вартість робіт у створених нарядах.
        total_parts_profit: Загальний прибуток з запчастин у створених нарядах
            (сума (ціна_продажу - ціна_закупівлі) × кількість).
        service_earnings: Нарахування за роботи.
        parts_earnings: Нарахування за запчастини.
        total_earnings: Загальне нарахування (роботи + запчастини).
    """

    employee: Any  # Employee
    labor_percent: Decimal
    parts_sale_percent: Decimal
    orders_count: int
    total_service_cost: Decimal
    total_parts_profit: Decimal
    service_earnings: Decimal
    parts_earnings: Decimal
    total_earnings: Decimal


def get_all_managers_summary(
    company: Any,  # Company
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[ManagerSummaryRow]:
    """Повертає зведений звіт по зарплаті всіх менеджерів компанії.

    Для кожного співробітника з роллю 'manager' підраховує кількість
    створених нарядів, загальну вартість робіт та прибуток з запчастин
    у цих нарядах, а також нарахування за формулами:
    - `service_cost × labor_percent / 100`
    - `parts_profit × parts_sale_percent / 100`
      (прибуток = (ціна_продажу - ціна_закупівлі) × кількість)

    Args:
        company: Компанія, для якої формується звіт.
        date_from: Початкова дата створення наряду (опціонально).
        date_to: Кінцева дата створення наряду (опціонально).

    Returns:
        Список ManagerSummaryRow, відсортований за нарахуванням (спадання).
    """
    from accounts.models import Employee

    # Отримуємо всіх співробітників з роллю 'manager'
    managers: list[Employee] = list(
        Employee.objects.filter(
            company=company,
            roles__codename='manager',
        ).select_related('user').prefetch_related('roles'),
    )

    from django.db.models import Sum, ExpressionWrapper, F, DecimalField

    rows: list[ManagerSummaryRow] = []
    for manager in managers:
        # Усі наряди, створені цим менеджером
        wo_qs = WorkOrder.objects.filter(
            created_by=manager,
        )
        if date_from is not None:
            wo_qs = wo_qs.filter(created_at__date__gte=date_from)
        if date_to is not None:
            wo_qs = wo_qs.filter(created_at__date__lte=date_to)

        orders_count: int = wo_qs.count()

        # Загальна вартість робіт у цих нарядах
        svc_agg = WorkOrderService.objects.filter(
            work_order__in=wo_qs,
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('quantity') * F('unit_price'),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                ),
            ),
        )
        total_service_cost: Decimal = svc_agg['total'] or Decimal('0.00')

        # Загальний прибуток з запчастин у цих нарядах
        # Прибуток = Σ quantity × (unit_price - COALESCE(purchase_price, 0))
        from django.db.models import Value
        from django.db.models.functions import Coalesce

        part_agg = WorkOrderPart.objects.filter(
            work_order__in=wo_qs,
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('quantity') * (
                        F('unit_price')
                        - Coalesce(F('purchase_price'), Value(0, output_field=DecimalField()))
                    ),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                ),
            ),
        )
        total_parts_profit: Decimal = part_agg['total'] or Decimal('0.00')

        labor_pct: Decimal = manager.labor_percent or Decimal('0.00')
        parts_pct: Decimal = manager.parts_sale_percent or Decimal('0.00')

        service_earnings: Decimal = Decimal('0.00')
        if labor_pct > Decimal('0.00') and total_service_cost > Decimal('0.00'):
            service_earnings = (
                total_service_cost * labor_pct / Decimal('100')
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        parts_earnings: Decimal = Decimal('0.00')
        if parts_pct > Decimal('0.00') and total_parts_profit > Decimal('0.00'):
            parts_earnings = (
                total_parts_profit * parts_pct / Decimal('100')
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        total_earnings: Decimal = (
            service_earnings + parts_earnings
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        rows.append(ManagerSummaryRow(
            employee=manager,
            labor_percent=labor_pct,
            parts_sale_percent=parts_pct,
            orders_count=orders_count,
            total_service_cost=total_service_cost.quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP,
            ),
            total_parts_profit=total_parts_profit.quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP,
            ),
            service_earnings=service_earnings,
            parts_earnings=parts_earnings,
            total_earnings=total_earnings,
        ))

    rows.sort(key=lambda r: r.total_earnings, reverse=True)
    return rows
