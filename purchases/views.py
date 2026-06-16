"""Представлення (views) для закупівлі запчастин."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import DatabaseError, transaction
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

logger = logging.getLogger('autoservice')

from accounts.utils import (
    filter_queryset_by_company,
    get_object_or_404_for_company,
    get_user_company,
    paginate_queryset,
)
from company.models import Company
from purchases.forms import (
    PurchaseOrderForm,
    PurchaseOrderItemFormSet,
    PurchaseReceiveForm,
    SupplierPaymentForm,
)
from purchases.models import PurchaseOrder, PurchaseOrderItem, SupplierPayment
from purchases.services import PurchaseOrderService, SupplierPaymentService
from suppliers.models import Supplier

from permissions.utils import permission_required


@permission_required('purchases', 'read')
def purchase_list(request: HttpRequest) -> HttpResponse:
    """
    Відображає список замовлень закупівлі.

    **Бізнес-логіка:**
    - Підтримує фільтр за постачальником через Query-параметр `supplier`.

    Returns:
        Відрендерений HTML-шаблон зі списком замовлень.
    """
    qs = filter_queryset_by_company(
        request,
        PurchaseOrder.objects.select_related('supplier', 'company'),
    )
    selected_supplier: Supplier | None = None
    supplier_pk: str | None = request.GET.get('supplier')
    if supplier_pk:
        try:
            pk: int = int(supplier_pk)
            selected_supplier = get_object_or_404(
                filter_queryset_by_company(
                    request,
                    Supplier.objects.select_related('company'),
                ),
                pk=pk,
            )
            qs = qs.filter(supplier=selected_supplier)
        except (ValueError, TypeError):
            selected_supplier = None
    page_obj = paginate_queryset(request, qs)
    return render(request, 'purchases/list.html', {
        'page_obj': page_obj,
        'selected_supplier': selected_supplier,
    })


@transaction.atomic
@permission_required('purchases', 'create')
def purchase_create(request: HttpRequest) -> HttpResponse:
    """
    Створює нове замовлення закупівлі з товарними позиціями.

    **Бізнес-логіка:**
    - Новому замовленню автоматично присвоюється статус **Чернетка (DRAFT)**
      та генерується унікальний номер `order_number` у форматі `PO-XXXXX`.
    - Позиції додаються через inline formset `PurchaseOrderItemFormSet`.
    - Якщо форма валідна, а formset — ні, щойно створене замовлення
      видаляється, щоб уникнути «осиротілих» замовлень без позицій.

    Side Effects:
        - Створює запис у таблиці `PurchaseOrder`.
        - Створює відповідні записи в `PurchaseOrderItem` (якщо formset валідний).
        - Якщо formset невалідний — щойно створений `PurchaseOrder` видаляється.
    """
    company = get_user_company(request)

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, company=company)
        if form.is_valid():
            purchase: PurchaseOrder = form.save(commit=False)
            purchase.status = PurchaseOrder.Status.DRAFT

            if request.user.is_authenticated:
                purchase.created_by = getattr(request.user, 'employee', None)

            if company:
                purchase.company = company

            purchase.save()

            formset = PurchaseOrderItemFormSet(
                request.POST, instance=purchase,
                form_kwargs={'company': company},
            )
            if formset.is_valid():
                formset.save()
                return redirect('purchase_detail', pk=purchase.pk)
            else:
                purchase.delete()
        else:
            formset = PurchaseOrderItemFormSet(
                request.POST, form_kwargs={'company': company},
            )
    else:
        form = PurchaseOrderForm(company=company)
        formset = PurchaseOrderItemFormSet(form_kwargs={'company': company})

    return render(request, 'purchases/form.html', {
        'form': form,
        'formset': formset,
        'title': 'Нове замовлення закупівлі',
    })


@permission_required('purchases', 'read')
def purchase_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Відображає деталі замовлення закупівлі зі списком позицій.

    Args:
        pk: Первинний ключ замовлення закупівлі.
    """
    purchase: PurchaseOrder = get_object_or_404_for_company(
        request,
        PurchaseOrder.objects.select_related(
            'supplier', 'company', 'created_by__user',
        ),
        pk=pk,
    )
    items: list[PurchaseOrderItem] = list(
        purchase.items.select_related('part').all(),
    )
    return render(request, 'purchases/detail.html', {
        'purchase': purchase,
        'items': items,
    })


@transaction.atomic
@permission_required('purchases', 'edit')
def purchase_update(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Редагує замовлення закупівлі (тільки в статусі **Чернетка**).

    **Бізнес-логіка:**
    - На GET-запитах (відкриття форми) блокування рядка НЕ застосовується.
    - На POST-запитах (збереження) використовується `select_for_update(nowait=True)`.
    - Редагування доступне лише для замовлень у статусі **DRAFT**.
    """
    qs = filter_queryset_by_company(request, PurchaseOrder.objects.all())
    if request.method == 'POST':
        try:
            qs = qs.select_for_update(nowait=True)
        except DatabaseError:
            return render(request, 'purchases/error.html', {
                'message': 'Замовлення зараз редагується іншим користувачем. Спробуйте пізніше.',
            }, status=409)

    purchase: PurchaseOrder = get_object_or_404(
        qs,
        pk=pk,
    )

    if not purchase.is_editable:
        return render(request, 'purchases/error.html', {
            'message': 'Не можна редагувати замовлення в статусі '
                       f'«{purchase.get_status_display()}». '
                       'Редагування доступне лише для чернеток.',
        }, status=403)

    company = get_user_company(request)

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=purchase, company=company)
        formset = PurchaseOrderItemFormSet(
            request.POST, instance=purchase,
            form_kwargs={'company': company},
        )
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('purchase_detail', pk=purchase.pk)
    else:
        form = PurchaseOrderForm(instance=purchase, company=company)
        formset = PurchaseOrderItemFormSet(
            instance=purchase,
            form_kwargs={'company': company},
        )

    return render(request, 'purchases/form.html', {
        'form': form,
        'formset': formset,
        'title': f'Редагувати {purchase.order_number}',
    })


@transaction.atomic
@require_POST
@permission_required('purchases', 'edit')
def purchase_submit(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Переводить замовлення зі статусу **Чернетка (DRAFT)** у **Замовлено (ORDERED)**.

    **Бізнес-логіка:**
    - Декоратор `@require_POST` гарантує, що ця функція реагує лише на POST-запити.
    - Використовує блокування рядка (`select_for_update(nowait=True)`).
    - Замовлення без жодної позиції не може бути відправлене.
    """
    try:
        purchase_qs = filter_queryset_by_company(
            request, PurchaseOrder.objects.all(),
        ).select_for_update(nowait=True)
    except DatabaseError:
        return render(request, 'purchases/error.html', {
            'message': 'Замовлення зараз редагується іншим користувачем. Спробуйте пізніше.',
        }, status=409)
    purchase: PurchaseOrder = get_object_or_404(
        purchase_qs,
        pk=pk,
    )

    if purchase.status != PurchaseOrder.Status.DRAFT:
        return render(request, 'purchases/error.html', {
            'message': 'Можна відправити лише замовлення в статусі «Чернетка».',
        }, status=403)

    if not purchase.items.exists():
        return render(request, 'purchases/error.html', {
            'message': 'Не можна відправити замовлення без позицій.',
        }, status=400)

    purchase.status = PurchaseOrder.Status.ORDERED
    purchase.save(update_fields=['status'])
    logger.info(
        'Purchase submitted. User: %s, Order: %s, Company: %s',
        request.user, purchase.order_number, purchase.company_id,
    )
    return redirect('purchase_detail', pk=purchase.pk)


@transaction.atomic
@permission_required('purchases', 'edit')
def purchase_receive(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Оприбутковує товар за замовленням — оновлює кількість на складі.

    **Бізнес-логіка:**
    - Використовує `select_for_update(nowait=True)` та `F()` вирази
      для захисту від стану перегону.

    Side Effects:
        - Оновлює `PurchaseOrderItem.quantity_received` (атомарно через `F()`).
        - Змінює статус замовлення:
          * **Отримано (RECEIVED)** — якщо всі позиції отримані повністю.
          * **Частково отримано (PARTIALLY_RECEIVED)** — якщо є позиції на очікуванні.
    """
    purchase: PurchaseOrder = get_object_or_404_for_company(
        request,
        PurchaseOrder.objects.select_related('supplier', 'company'),
        pk=pk,
    )

    if not purchase.is_receivable:
        return render(request, 'purchases/error.html', {
            'message': 'Не можна приймати товар для замовлення в статусі '
                       f'«{purchase.get_status_display()}».',
        }, status=403)

    # Отримуємо позиції, які ще не повністю оприбутковані
    items_qs = purchase.items.filter(
        quantity_received__lt=F('quantity_ordered'),
    ).select_related('part')

    # Lock items FIRST to prevent TOCTOU race condition
    try:
        locked_qs = PurchaseOrderItem.objects.filter(
            pk__in=items_qs.values('pk'),
        ).select_for_update(nowait=True)
    except DatabaseError:
        return render(request, 'purchases/error.html', {
            'message': 'Замовлення зараз редагується іншим користувачем. Спробуйте пізніше.',
        }, status=409)

    # Один запит — без попереднього .exists()
    items: list[PurchaseOrderItem] = list(items_qs)
    if not items:
        return redirect('purchase_detail', pk=purchase.pk)

    if request.method == 'POST':
        # Переконуємося, що всі позиції досі актуальні (не були змінені)
        if len(items) != len(locked_qs):
            return render(request, 'purchases/error.html', {
                'message': 'Дані замовлення змінилися. Спробуйте ще раз.',
            }, status=409)

        form = PurchaseReceiveForm(request.POST, items=items)
        if form.is_valid():
            received_data: list[tuple[PurchaseOrderItem, Decimal]] = (
                form.get_receive_data()
            )
            PurchaseOrderService.receive_items(purchase, received_data)
            logger.info(
                'Purchase received. User: %s, Order: %s, Company: %s',
                request.user, purchase.order_number, purchase.company_id,
            )
            return redirect('purchase_detail', pk=purchase.pk)
    else:
        form = PurchaseReceiveForm(items=items)

    return render(request, 'purchases/receive.html', {
        'purchase': purchase,
        'form': form,
    })


@transaction.atomic
@permission_required('purchases', 'edit')
def purchase_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Скасовує замовлення — переводить у статус **Скасовано (CANCELLED)**.

    **Бізнес-логіка:**
    - Скасувати можна лише замовлення в статусі **Чернетка (DRAFT)**
      або **Замовлено (ORDERED)**. Якщо товар уже хоча б частково
      оприбутковано — скасування заборонене.
    """
    qs = filter_queryset_by_company(request, PurchaseOrder.objects.all())
    if request.method == 'POST':
        try:
            qs = qs.select_for_update(nowait=True)
        except DatabaseError:
            return render(request, 'purchases/error.html', {
                'message': 'Замовлення зараз редагується іншим користувачем. Спробуйте пізніше.',
            }, status=409)

    purchase: PurchaseOrder = get_object_or_404(
        qs,
        pk=pk,
    )

    if purchase.status in (PurchaseOrder.Status.RECEIVED, PurchaseOrder.Status.CANCELLED):
        return render(request, 'purchases/error.html', {
            'message': 'Не можна скасувати замовлення в статусі '
                       f'«{purchase.get_status_display()}».',
        }, status=403)

    if request.method == 'POST':
        purchase.status = PurchaseOrder.Status.CANCELLED
        purchase.save(update_fields=['status'])
        logger.warning(
            'Purchase CANCELLED. User: %s, Order: %s, Company: %s',
            request.user, purchase.order_number, purchase.company_id,
        )
        return redirect('purchase_list')

    return render(request, 'purchases/confirm_delete.html', {
        'purchase': purchase,
        'action': 'скасувати',
        'action_url': 'purchase_cancel',
    })


@transaction.atomic
@permission_required('purchases', 'delete')
def purchase_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Видаляє замовлення закупівлі (тільки в статусі **Чернетка**).

    **Бізнес-логіка:**
    - Видалити можна лише замовлення, яке ще не відправлене (статус **DRAFT**).
    """
    qs = filter_queryset_by_company(request, PurchaseOrder.objects.all())
    if request.method == 'POST':
        try:
            qs = qs.select_for_update(nowait=True)
        except DatabaseError:
            return render(request, 'purchases/error.html', {
                'message': 'Замовлення зараз редагується іншим користувачем. Спробуйте пізніше.',
            }, status=409)

    purchase: PurchaseOrder = get_object_or_404(
        qs,
        pk=pk,
    )

    if not purchase.is_editable:
        return render(request, 'purchases/error.html', {
            'message': 'Можна видалити лише замовлення в статусі «Чернетка».',
        }, status=403)

    if request.method == 'POST':
        order_number: str = purchase.order_number
        company_id: int = purchase.company_id
        purchase.delete()
        logger.warning(
            'Purchase DELETED. User: %s, Order: %s, Company: %s',
            request.user, order_number, company_id,
        )
        return redirect('purchase_list')

    return render(request, 'purchases/confirm_delete.html', {
        'purchase': purchase,
        'action': 'видалити',
        'action_url': 'purchase_delete',
    })


# ============================================================
# ПЛАТЕЖІ ПОСТАЧАЛЬНИКАМ
# ============================================================


@permission_required('payments', 'read')
def payment_list(request: HttpRequest) -> HttpResponse:
    """Відображає список платежів постачальникам.

    Підтримує фільтрацію за постачальником та діапазоном дат.
    За замовчуванням показує платежі за останній місяць.
    """
    qs = filter_queryset_by_company(
        request,
        SupplierPayment.objects.select_related(
            'supplier', 'company', 'created_by__user',
        ),
    )

    today_dt: datetime = timezone.now()
    default_from: datetime = today_dt - timedelta(days=30)

    date_from_str: str = request.GET.get('date_from', '')
    date_to_str: str = request.GET.get('date_to', '')

    try:
        filter_from: date = datetime.strptime(
            date_from_str, '%Y-%m-%d',
        ).date() if date_from_str else default_from.date()
    except (ValueError, TypeError):
        filter_from = default_from.date()

    try:
        filter_to: date = datetime.strptime(
            date_to_str, '%Y-%m-%d',
        ).date() if date_to_str else today_dt.date()
    except (ValueError, TypeError):
        filter_to = today_dt.date()

    qs = qs.filter(payment_date__gte=filter_from, payment_date__lte=filter_to)

    supplier_pk: str | None = request.GET.get('supplier')
    selected_supplier: Supplier | None = None
    if supplier_pk:
        try:
            pk: int = int(supplier_pk)
            selected_supplier = get_object_or_404(
                filter_queryset_by_company(
                    request,
                    Supplier.objects.select_related('company'),
                ),
                pk=pk,
            )
            qs = qs.filter(supplier=selected_supplier)
        except (ValueError, TypeError):
            selected_supplier = None

    page_obj = paginate_queryset(request, qs)

    # Список постачальників для фільтра (тільки своєї компанії)
    suppliers_list = list(
        filter_queryset_by_company(
            request, Supplier.objects.select_related('company'),
        ).order_by('name'),
    )

    return render(request, 'purchases/payment_list.html', {
        'page_obj': page_obj,
        'selected_supplier': selected_supplier,
        'suppliers': suppliers_list,
        'filter_from': filter_from,
        'filter_to': filter_to,
    })


@transaction.atomic
@permission_required('payments', 'create')
def payment_create(request: HttpRequest) -> HttpResponse:
    """Створює новий платіж постачальнику.

    За замовчуванням встановлює сьогоднішню дату.
    """
    # Витягуємо ID постачальника з POST або GET
    supplier_id: int | None = None
    raw_supplier: str | None = (
        request.POST.get('supplier') or request.GET.get('supplier')
    )
    if raw_supplier:
        try:
            supplier_id = int(raw_supplier)
        except (ValueError, TypeError):
            supplier_id = None

    company = get_user_company(request)

    if request.method == 'POST':
        form = SupplierPaymentForm(
            request.POST, supplier_id=supplier_id, company=company,
        )
        if form.is_valid():
            payment: SupplierPayment = form.save(commit=False)

            if request.user.is_authenticated:
                payment.created_by = getattr(request.user, 'employee', None)

            if company:
                payment.company = company

            payment.save()
            logger.info(
                'Payment created. User: %s, Supplier: %s, Amount: %s',
                request.user, payment.supplier_id, payment.amount,
            )
            return redirect('payment_list')
    else:
        initial: dict[str, object] = {
            'payment_date': timezone.now().date(),
        }
        if supplier_id:
            initial['supplier'] = supplier_id
        form = SupplierPaymentForm(
            initial=initial, supplier_id=supplier_id, company=company,
        )

    # Дані для JS-фільтрації замовлень за постачальником
    po_qs = filter_queryset_by_company(request, PurchaseOrder.objects.all())
    po_qs = po_qs.annotate(
        _total_amount=Coalesce(
            Sum(F('items__quantity_ordered') * F('items__unit_price')),
            Value(0.00),
            output_field=DecimalField(),
        ),
    )
    purchase_orders_json: dict[str, list[dict[str, str]]] = {}
    for po in po_qs.order_by('order_number').values(
        'id', 'order_number', 'supplier_id', '_total_amount',
    ):
        sid: str = str(po['supplier_id'])
        amount: float = float(po['_total_amount'])
        purchase_orders_json.setdefault(sid, [])
        purchase_orders_json[sid].append({
            'value': str(po['id']),
            'label': f'{po["order_number"]} — {amount:,.2f} грн',
        })

    return render(request, 'purchases/payment_form.html', {
        'form': form,
        'title': 'Новий платіж',
        'purchase_orders_json': purchase_orders_json,
    })


@transaction.atomic
@permission_required('payments', 'edit')
def payment_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує або переглядає платіж постачальнику.

    Проведені платежі (status=COMPLETED) не можна редагувати —
    при POST-запиті повертається помилка; при GET-запиті
    всі поля форми відображаються в режимі "лише для читання".

    Args:
        pk: Первинний ключ платежу.
    """
    payment: SupplierPayment = get_object_or_404_for_company(
        request,
        SupplierPayment.objects.select_related(
            'supplier', 'company',
        ),
        pk=pk,
    )

    supplier_id: int | None = payment.supplier_id
    company = get_user_company(request)

    # Заборона редагування проведених платежів
    payment_completed: bool = payment.status == SupplierPayment.Status.COMPLETED
    if payment_completed and request.method == 'POST':
        return render(request, 'purchases/error.html', {
            'message': 'Не можна редагувати проведений платіж. '
                       'Створіть новий платіж або скасуйте поточний.',
        }, status=403)

    if request.method == 'POST':
        form = SupplierPaymentForm(
            request.POST, instance=payment, supplier_id=supplier_id,
            company=company,
        )
        if form.is_valid():
            form.save()
            logger.info(
                'Payment updated. User: %s, Payment: %s',
                request.user, payment.pk,
            )
            return redirect('payment_list')
    else:
        form = SupplierPaymentForm(
            instance=payment, supplier_id=supplier_id, company=company,
        )
        # Для проведених платежів — всі поля тільки для читання
        if payment_completed:
            for field_name in form.fields:
                form.fields[field_name].disabled = True

    # Дані для JS-фільтрації замовлень за постачальником
    po_qs = filter_queryset_by_company(request, PurchaseOrder.objects.all())
    po_qs = po_qs.annotate(
        _total_amount=Coalesce(
            Sum(F('items__quantity_ordered') * F('items__unit_price')),
            Value(0.00),
            output_field=DecimalField(),
        ),
    )
    purchase_orders_json: dict[str, list[dict[str, str]]] = {}
    for po in po_qs.order_by('order_number').values(
        'id', 'order_number', 'supplier_id', '_total_amount',
    ):
        sid: str = str(po['supplier_id'])
        amount: float = float(po['_total_amount'])
        purchase_orders_json.setdefault(sid, [])
        purchase_orders_json[sid].append({
            'value': str(po['id']),
            'label': f'{po["order_number"]} — {amount:,.2f} грн',
        })

    return render(request, 'purchases/payment_form.html', {
        'form': form,
        'title': 'Редагувати платіж',
        'purchase_orders_json': purchase_orders_json,
        'payment_completed': payment_completed,
    })


@transaction.atomic
@permission_required('payments', 'delete')
def payment_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє платіж постачальнику.

    Args:
        pk: Первинний ключ платежу.
    """
    payment: SupplierPayment = get_object_or_404_for_company(
        request, SupplierPayment, pk=pk,
    )

    # Заборона видалення проведених платежів
    if payment.status == SupplierPayment.Status.COMPLETED:
        return render(request, 'purchases/error.html', {
            'message': 'Не можна видалити проведений платіж. '
                       'Спочатку скасуйте платіж.',
        }, status=403)

    if request.method == 'POST':
        supplier_name: str = payment.supplier.name
        amount: Decimal = payment.amount
        payment.delete()
        logger.warning(
            'Payment DELETED. User: %s, Supplier: %s, Amount: %s',
            request.user, supplier_name, amount,
        )
        return redirect('payment_list')

    return render(request, 'purchases/payment_confirm_delete.html', {
        'payment': payment,
    })
