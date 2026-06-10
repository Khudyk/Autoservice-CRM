"""Представлення (views) для закупівлі запчастин з ізоляцією даних."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
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
    get_user_company,
    has_purchase_edit_permission,
    has_purchase_permission,
    is_admin_user,
    paginate_queryset,
    prepare_list_context,
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


@login_required
def purchase_list(request: HttpRequest) -> HttpResponse:
    """
    Відображає список замовлень закупівлі з ізоляцією за компанією.

    **Бізнес-логіка:**
    - Доступно лише директорам та адміністраторам.
    - Адміністратори бачать замовлення всіх компаній і можуть фільтрувати
      список за конкретною компанією через Query-параметр `company`.
    - Підтримує фільтр за постачальником через Query-параметр `supplier`.
      Якщо постачальника вказано, список обмежується замовленнями
      тільки від цього постачальника (з урахуванням multi-tenant ізоляції).

    Raises:
        PermissionDenied: Якщо користувач не має права переглядати закупівлі.
        Http404: Якщо постачальник з вказаним PK не знайдений або не належить
                 до компанії користувача.

    Returns:
        Відрендерений HTML-шаблон зі списком замовлень, переліком компаній
        для фільтрації та обраною компанією (якщо застосовано фільтр).
    """
    if not has_purchase_permission(request=request):
        raise PermissionDenied(
            'Перегляд закупівель доступний лише директорам та адміністраторам.',
        )
    qs = PurchaseOrder.objects.select_related('supplier', 'company')
    qs, companies, selected_company = prepare_list_context(request, qs)
    selected_supplier: Supplier | None = None
    supplier_pk: str | None = request.GET.get('supplier')
    if supplier_pk:
        try:
            pk: int = int(supplier_pk)
            selected_supplier = get_object_or_404(
                filter_queryset_by_company(
                    request, Supplier.objects.select_related('company'),
                ),
                pk=pk,
            )
            qs = qs.filter(supplier=selected_supplier)
        except (ValueError, TypeError):
            selected_supplier = None
    page_obj = paginate_queryset(request, qs)
    can_edit: bool = has_purchase_edit_permission(request=request)
    return render(request, 'purchases/list.html', {
        'page_obj': page_obj,
        'companies': companies,
        'selected_company': selected_company,
        'selected_supplier': selected_supplier,
        'can_edit': can_edit,
    })


@login_required
@transaction.atomic
def purchase_create(request: HttpRequest) -> HttpResponse:
    """
    Створює нове замовлення закупівлі з товарними позиціями.

    **Бізнес-логіка:**
    - Доступно лише директорам та адміністраторам.
    - Адміністратори можуть вибрати будь-яку компанію з випадаючого списку.
    - Звичайні користувачі створюють замовлення виключно для своєї компанії;
      поле `company` для них блокується.
    - Новому замовленню автоматично присвоюється статус **Чернетка (DRAFT)**
      та генерується унікальний номер `order_number` у форматі `PO-XXXXX`
      у межах компанії.
    - Позиції додаються через inline formset `PurchaseOrderItemFormSet`.
    - Якщо форма валідна, а formset — ні, щойно створене замовлення
      видаляється, щоб уникнути «осиротілих» замовлень без позицій.

    Side Effects:
        - Створює запис у таблиці `PurchaseOrder`.
        - Створює відповідні записи в `PurchaseOrderItem` (якщо formset валідний).
        - Якщо formset невалідний — щойно створений `PurchaseOrder` видаляється.

    Returns:
        У разі успіху — перенаправлення на сторінку деталей замовлення.
        Інакше — повторне відображення форми з помилками валідації.
    """
    if not has_purchase_edit_permission(request=request):
        raise PermissionDenied(
            'Створення закупівель доступне лише директорам, адміністраторам, '
            'менеджерам та закупівельникам.',
        )

    user_company: Company | None = get_user_company(request=request)

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            purchase: PurchaseOrder = form.save(commit=False)
            purchase.status = PurchaseOrder.Status.DRAFT

            if not is_admin_user(request=request) and user_company:
                purchase.company = user_company
            elif is_admin_user(request=request) and not purchase.company_id:
                purchase.company = user_company

            purchase.order_number = PurchaseOrder.generate_order_number(
                company_id=purchase.company_id,
            )

            if request.user.is_authenticated:
                purchase.created_by = getattr(request.user, 'employee', None)

            purchase.save()

            formset = PurchaseOrderItemFormSet(
                request.POST, instance=purchase,
            )
            if formset.is_valid():
                formset.save()
                return redirect('purchase_detail', pk=purchase.pk)
            else:
                purchase.delete()
        else:
            formset = PurchaseOrderItemFormSet(request.POST)
    else:
        form = PurchaseOrderForm()
        formset = PurchaseOrderItemFormSet()

    _configure_company_and_supplier_fields(
        request=request, form=form, user_company=user_company,
    )

    return render(request, 'purchases/form.html', {
        'form': form,
        'formset': formset,
        'title': 'Нове замовлення закупівлі',
    })


@login_required
def purchase_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Відображає деталі замовлення закупівлі зі списком позицій.

    **Бізнес-логіка:**
    - Доступно лише директорам та адміністраторам.
    - Завантажує замовлення разом із постачальником, компанією та
      відповідальним співробітником (через `select_related`).
    - Застосовує фільтр ізоляції за компанією: якщо замовлення не належить
      до компанії поточного користувача, повертається 404.

    Args:
        pk: Первинний ключ замовлення закупівлі.

    Returns:
        Відрендерений HTML-шаблон із детальною інформацією про замовлення
        та переліком його позицій.

    Raises:
        PermissionDenied: Якщо користувач не має права переглядати закупівлі.
        Http404: Якщо замовлення з таким PK не існує або не належить
                 до компанії користувача.
    """
    if not has_purchase_permission(request=request):
        raise PermissionDenied(
            'Перегляд закупівель доступний лише директорам та адміністраторам.',
        )
    purchase: PurchaseOrder = get_object_or_404(
        filter_queryset_by_company(
            request, PurchaseOrder.objects.select_related(
                'supplier', 'company', 'created_by__user',
            ),
        ),
        pk=pk,
    )
    items: list[PurchaseOrderItem] = list(
        purchase.items.select_related('part').all(),
    )
    can_edit: bool = has_purchase_edit_permission(request=request)
    return render(request, 'purchases/detail.html', {
        'purchase': purchase,
        'items': items,
        'can_edit': can_edit,
    })


@login_required
@transaction.atomic
def purchase_update(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Редагує замовлення закупівлі (тільки в статусі **Чернетка**).

    **Бізнес-логіка:**
    - Доступно лише директорам та адміністраторам.
    - На GET-запитах (відкриття форми) блокування рядка НЕ застосовується,
      щоб не блокувати інших користувачів під час заповнення форми.
    - На POST-запитах (збереження) використовується `select_for_update(nowait=True)`
      для блокування рядка. Якщо інший користувач уже редагує це замовлення,
      запит негайно отримає помилку блокування (DatabaseError).
    - Редагування доступне лише для замовлень у статусі **DRAFT**.
    - Поле `company` блокується для зміни, оскільки замовлення вже створене.

    Args:
        pk: Первинний ключ замовлення.

    Side Effects:
        - Оновлює поля замовлення (форма) та його позиції (formset).
        - Зміни фіксуються лише після успішного завершення транзакції.

    Returns:
        У разі успіху — перенаправлення на сторінку деталей замовлення.
        Інакше — повторне відображення форми з помилками.

    Raises:
        PermissionDenied: Якщо користувач не має права редагувати закупівлі.
        Http404: Якщо замовлення не знайдено або не належить компанії
                 користувача.
        django.db.utils.DatabaseError: Якщо `select_for_update(nowait=True)`
            не може отримати блокування рядка (інший користувач редагує).
    """
    if not has_purchase_edit_permission(request=request):
        raise PermissionDenied(
            'Редагування закупівель доступне лише директорам, адміністраторам, '
            'менеджерам та закупівельникам.',
        )

    qs = PurchaseOrder.objects.all()
    if request.method == 'POST':
        try:
            qs = qs.select_for_update(nowait=True)
        except DatabaseError:
            return render(request, 'purchases/error.html', {
                'message': 'Замовлення зараз редагується іншим користувачем. Спробуйте пізніше.',
            }, status=409)

    purchase: PurchaseOrder = get_object_or_404(
        filter_queryset_by_company(request, qs),
        pk=pk,
    )

    if not purchase.is_editable:
        return render(request, 'purchases/error.html', {
            'message': 'Не можна редагувати замовлення в статусі '
                       f'«{purchase.get_status_display()}». '
                       'Редагування доступне лише для чернеток.',
        }, status=403)

    user_company: Company | None = get_user_company(request=request)

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=purchase)
        formset = PurchaseOrderItemFormSet(request.POST, instance=purchase)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('purchase_detail', pk=purchase.pk)
    else:
        form = PurchaseOrderForm(instance=purchase)
        formset = PurchaseOrderItemFormSet(instance=purchase)

    _configure_company_and_supplier_fields(
        request=request, form=form, user_company=user_company,
    )
    form.fields['company'].disabled = True

    return render(request, 'purchases/form.html', {
        'form': form,
        'formset': formset,
        'title': f'Редагувати {purchase.order_number}',
    })


@login_required
@transaction.atomic
@require_POST
def purchase_submit(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Переводить замовлення зі статусу **Чернетка (DRAFT)** у **Замовлено (ORDERED)**.

    **Бізнес-логіка:**
    - Доступно лише директорам та адміністраторам.
    - Декоратор `@require_POST` гарантує, що ця функція реагує лише на
      POST-запити. GET-запити отримують помилку 405 (Method Not Allowed),
      що запобігає випадковому відправленню замовлення через перехід
      за посиланням.
    - Використовує блокування рядка (`select_for_update(nowait=True)`),
      щоб запобігти **подвійному відправленню (double-submit)**.
    - Замовлення без жодної позиції не може бути відправлене — повертається
      помилка 400.

    Args:
        pk: Первинний ключ замовлення.

    Side Effects:
        - Змінює статус замовлення на `ORDERED`.
        - Після відправлення замовлення стає недоступним для редагування
          та видалення — доступне лише оприбуткування або скасування.

    Returns:
        У разі успіху — перенаправлення на сторінку деталей замовлення.

    Raises:
        PermissionDenied: Якщо користувач не має права працювати з закупівлями.
        Http404: Якщо замовлення не знайдено або не належить компанії
                 користувача.
        django.db.utils.DatabaseError: Якщо `select_for_update(nowait=True)`
            не може отримати блокування рядка.
    """
    if not has_purchase_edit_permission(request=request):
        raise PermissionDenied(
            'Відправлення закупівель доступне лише директорам, адміністраторам, '
            'менеджерам та закупівельникам.',
        )
    try:
        purchase_qs = PurchaseOrder.objects.select_for_update(nowait=True)
    except DatabaseError:
        return render(request, 'purchases/error.html', {
            'message': 'Замовлення зараз редагується іншим користувачем. Спробуйте пізніше.',
        }, status=409)
    purchase: PurchaseOrder = get_object_or_404(
        filter_queryset_by_company(request, purchase_qs),
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


@login_required
@transaction.atomic
def purchase_receive(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Оприбутковує товар за замовленням — оновлює кількість на складі.

    **Бізнес-логіка:**
    - Доступно лише директорам та адміністраторам.
    - Це найкритичніша операція з погляду цілісності даних, оскільки вона
      одночасно змінює дві сутності: кількість отриманого в позиції замовлення
      та складський залишок запчастини. Без належної ізоляції можливі:

      1. **Втрата оновлень (lost update)** — два одночасних оприбуткування
         читають однакове значення `quantity_received`, додають свою кількість
         і записують менше значення, ніж очікувалося.
      2. **Подвійне оприбуткування** — один і той самий товар може бути
         прийнятий двічі, якщо обидва запити пройдуть перевірку до зміни статусу.

    **Механізми захисту:**
    - `select_for_update(nowait=True)` — блокує рядки позицій лише на POST
      (фактичне оприбуткування). На GET (відображення форми) блокування
      не застосовується.
    - `F()` вирази — оновлення `quantity_received`
      виконується атомарно на рівні СУБД.
    - Перевірка `remaining_to_receive` виконується на стороні Python
      без додаткових запитів до БД, оскільки рядки вже заблоковані
      і дані актуальні.

    Args:
        pk: Первинний ключ замовлення.

    Side Effects:
        - Оновлює `PurchaseOrderItem.quantity_received` (атомарно через `F()`).
        - Змінює статус замовлення:
          * **Отримано (RECEIVED)** — якщо всі позиції отримані повністю.
          * **Частково отримано (PARTIALLY_RECEIVED)** — якщо є позиції,
            які ще очікуються.

    Returns:
        У разі успіху — перенаправлення на сторінку деталей замовлення.
        Якщо всі позиції вже отримані — перенаправлення без змін.
        Інакше — форма для введення кількості отриманого товару.

    Raises:
        PermissionDenied: Якщо користувач не має права працювати з закупівлями.
        Http404: Якщо замовлення не знайдено або не належить компанії
                 користувача.
        django.db.utils.DatabaseError: Якщо `select_for_update(nowait=True)`
            не може отримати блокування рядка позиції.
    """
    if not has_purchase_permission(request=request):
        raise PermissionDenied(
            'Оприбуткування закупівель доступне лише директорам та адміністраторам.',
        )
    purchase: PurchaseOrder = get_object_or_404(
        filter_queryset_by_company(
            request, PurchaseOrder.objects.select_related('supplier', 'company'),
        ),
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


@login_required
@transaction.atomic
def purchase_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Скасовує замовлення — переводить у статус **Скасовано (CANCELLED)**.

    **Бізнес-логіка:**
    - Доступно лише директорам та адміністраторам.
    - Скасувати можна лише замовлення в статусі **Чернетка (DRAFT)**
      або **Замовлено (ORDERED)**. Якщо товар уже хоча б частково
      оприбутковано — скасування заборонене.
    - На GET-запитах (сторінка підтвердження) блокування рядка НЕ
      застосовується. На POST-запитах (фактичне скасування) використовується
      `select_for_update(nowait=True)` для запобігання подвійному скасуванню.

    Args:
        pk: Первинний ключ замовлення.

    Side Effects:
        - Змінює статус замовлення на `CANCELLED`.
        - Скасоване замовлення більше не може бути змінене, відправлене
          або оприбутковане.

    Returns:
        GET — сторінка підтвердження скасування.
        POST — перенаправлення на список замовлень після скасування.

    Raises:
        PermissionDenied: Якщо користувач не має права працювати з закупівлями.
        Http404: Якщо замовлення не знайдено або не належить компанії
                 користувача.
        django.db.utils.DatabaseError: Якщо `select_for_update(nowait=True)`
            не може отримати блокування рядка.
    """
    if not has_purchase_edit_permission(request=request):
        raise PermissionDenied(
            'Скасування закупівель доступне лише директорам, адміністраторам, '
            'менеджерам та закупівельникам.',
        )
    qs = PurchaseOrder.objects.all()
    if request.method == 'POST':
        try:
            qs = qs.select_for_update(nowait=True)
        except DatabaseError:
            return render(request, 'purchases/error.html', {
                'message': 'Замовлення зараз редагується іншим користувачем. Спробуйте пізніше.',
            }, status=409)

    purchase: PurchaseOrder = get_object_or_404(
        filter_queryset_by_company(request, qs),
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


@login_required
@transaction.atomic
def purchase_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Видаляє замовлення закупівлі (тільки в статусі **Чернетка**).

    **Бізнес-логіка:**
    - Доступно лише директорам та адміністраторам.
    - Видалити можна лише замовлення, яке ще не відправлене
      (статус **DRAFT**).
    - На GET-запитах (сторінка підтвердження) блокування рядка НЕ
      застосовується. На POST-запитах (фактичне видалення) використовується
      `select_for_update(nowait=True)` для запобігання подвійному видаленню
      та стану перегону між редагуванням і видаленням.

    Args:
        pk: Первинний ключ замовлення.

    Side Effects:
        - Каскадно видаляє всі пов'язані позиції (`PurchaseOrderItem`).
        - Видалення не впливає на складські залишки, оскільки товар
          не був оприбуткований.

    Returns:
        GET — сторінка підтвердження видалення.
        POST — перенаправлення на список замовлень після видалення.

    Raises:
        PermissionDenied: Якщо користувач не має права працювати з закупівлями.
        Http404: Якщо замовлення не знайдено або не належить компанії
                 користувача.
        django.db.utils.DatabaseError: Якщо `select_for_update(nowait=True)`
            не може отримати блокування рядка.
    """
    if not has_purchase_edit_permission(request=request):
        raise PermissionDenied(
            'Видалення закупівель доступне лише директорам, адміністраторам, '
            'менеджерам та закупівельникам.',
        )
    qs = PurchaseOrder.objects.all()
    if request.method == 'POST':
        try:
            qs = qs.select_for_update(nowait=True)
        except DatabaseError:
            return render(request, 'purchases/error.html', {
                'message': 'Замовлення зараз редагується іншим користувачем. Спробуйте пізніше.',
            }, status=409)

    purchase: PurchaseOrder = get_object_or_404(
        filter_queryset_by_company(request, qs),
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


@login_required
def payment_list(request: HttpRequest) -> HttpResponse:
    """Відображає список платежів постачальникам.

    **Бізнес-логіка:**
    - Доступно лише користувачам з правом перегляду закупівель.
    - Підтримує фільтрацію за постачальником та діапазоном дат.
    - За замовчуванням показує платежі за останній місяць.
    """
    if not has_purchase_permission(request=request):
        raise PermissionDenied(
            'Перегляд платежів доступний лише директорам, адміністраторам, '
            'менеджерам, закупівельникам та складовщикам.',
        )

    qs = SupplierPayment.objects.select_related(
        'supplier', 'company', 'created_by__user',
    )
    qs, companies, selected_company = prepare_list_context(request, qs)

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
                    request, Supplier.objects.select_related('company'),
                ),
                pk=pk,
            )
            qs = qs.filter(supplier=selected_supplier)
        except (ValueError, TypeError):
            selected_supplier = None

    page_obj = paginate_queryset(request, qs)
    can_edit: bool = has_purchase_edit_permission(request=request)

    # Список постачальників для фільтра (з урахуванням вибраної компанії)
    supplier_qs = Supplier.objects.select_related('company')
    if selected_company:
        supplier_qs = supplier_qs.filter(company=selected_company)
    suppliers_list = list(supplier_qs.order_by('name'))

    return render(request, 'purchases/payment_list.html', {
        'page_obj': page_obj,
        'companies': companies,
        'selected_company': selected_company,
        'selected_supplier': selected_supplier,
        'suppliers': suppliers_list,
        'filter_from': filter_from,
        'filter_to': filter_to,
        'can_edit': can_edit,
    })


@login_required
@transaction.atomic
def payment_create(request: HttpRequest) -> HttpResponse:
    """Створює новий платіж постачальнику.

    **Бізнес-логіка:**
    - Доступно лише редакторам закупівель.
    - За замовчуванням встановлює сьогоднішню дату.
    - Для адміністраторів доступний вибір будь-якої компанії.
    """
    if not has_purchase_edit_permission(request=request):
        raise PermissionDenied(
            'Створення платежів доступне лише директорам, адміністраторам, '
            'менеджерам та закупівельникам.',
        )

    user_company: Company | None = get_user_company(request=request)

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

    if request.method == 'POST':
        form = SupplierPaymentForm(request.POST, supplier_id=supplier_id)
        _configure_payment_form_fields(
            request=request, form=form, user_company=user_company,
            supplier_id=supplier_id,
        )
        if form.is_valid():
            payment: SupplierPayment = form.save(commit=False)

            if not is_admin_user(request=request) and user_company:
                payment.company = user_company
            elif is_admin_user(request=request) and not payment.company_id:
                payment.company = user_company

            # Автоматично генеруємо номер платежу
            payment.payment_number = SupplierPayment.generate_payment_number(
                payment.company_id,
            )

            if request.user.is_authenticated:
                payment.created_by = getattr(request.user, 'employee', None)

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
            initial=initial, supplier_id=supplier_id,
        )
        _configure_payment_form_fields(
            request=request, form=form, user_company=user_company,
            supplier_id=supplier_id,
        )

    # Дані для JS-фільтрації замовлень за постачальником
    po_qs = PurchaseOrder.objects.all()
    if not is_admin_user(request=request) and user_company:
        po_qs = po_qs.filter(company=user_company)
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


@login_required
@transaction.atomic
def payment_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Редагує або переглядає платіж постачальнику.

    Проведені платежі (status=COMPLETED) не можна редагувати —
    при POST-запиті повертається PermissionDenied; при GET-запиті
    всі поля форми відображаються в режимі "лише для читання".

    Args:
        pk: Первинний ключ платежу.

    Raises:
        PermissionDenied: Якщо користувач не має права редагувати
            або намагається змінити проведений платіж.
    """
    if not has_purchase_edit_permission(request=request):
        raise PermissionDenied(
            'Редагування платежів доступне лише директорам, адміністраторам, '
            'менеджерам та закупівельникам.',
        )

    payment: SupplierPayment = get_object_or_404(
        filter_queryset_by_company(
            request, SupplierPayment.objects.select_related(
                'supplier', 'company',
            ),
        ),
        pk=pk,
    )

    user_company: Company | None = get_user_company(request=request)
    # Фільтруємо замовлення за постачальником цього платежу
    supplier_id: int | None = payment.supplier_id

    # Заборона редагування проведених платежів
    payment_completed: bool = payment.status == SupplierPayment.Status.COMPLETED
    if payment_completed and request.method == 'POST':
        raise PermissionDenied(
            'Не можна редагувати проведений платіж. '
            'Створіть новий платіж або скасуйте поточний.',
        )

    if request.method == 'POST':
        form = SupplierPaymentForm(
            request.POST, instance=payment, supplier_id=supplier_id,
        )
        _configure_payment_form_fields(
            request=request, form=form, user_company=user_company,
            supplier_id=supplier_id,
        )
        form.fields['company'].disabled = True
        if form.is_valid():
            form.save()
            logger.info(
                'Payment updated. User: %s, Payment: %s',
                request.user, payment.pk,
            )
            return redirect('payment_list')
    else:
        form = SupplierPaymentForm(
            instance=payment, supplier_id=supplier_id,
        )
        _configure_payment_form_fields(
            request=request, form=form, user_company=user_company,
            supplier_id=supplier_id,
        )
        form.fields['company'].disabled = True
        # Для проведених платежів — всі поля тільки для читання
        if payment_completed:
            for field_name in form.fields:
                form.fields[field_name].disabled = True

    # Дані для JS-фільтрації замовлень за постачальником
    po_qs = PurchaseOrder.objects.all()
    if not is_admin_user(request=request) and user_company:
        po_qs = po_qs.filter(company=user_company)
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


@login_required
@transaction.atomic
def payment_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Видаляє платіж постачальнику.

    Args:
        pk: Первинний ключ платежу.

    Raises:
        PermissionDenied: Якщо користувач не має права видаляти.
    """
    if not has_purchase_edit_permission(request=request):
        raise PermissionDenied(
            'Видалення платежів доступне лише директорам, адміністраторам, '
            'менеджерам та закупівельникам.',
        )

    payment: SupplierPayment = get_object_or_404(
        filter_queryset_by_company(
            request, SupplierPayment.objects.all(),
        ),
        pk=pk,
    )

    # Заборона видалення проведених платежів
    if payment.status == SupplierPayment.Status.COMPLETED:
        raise PermissionDenied(
            'Не можна видалити проведений платіж. '
            'Спочатку скасуйте платіж.',
        )

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


# --- Допоміжні функції ---

def _configure_company_and_supplier_fields(
    request: HttpRequest,
    form: PurchaseOrderForm,
    user_company: Company | None,
) -> None:
    """
    Налаштовує поля `company` та `supplier` форми залежно від прав користувача.

    **Бізнес-логіка:**
    - Для звичайних користувачів поле `company` блокується та обмежується
      їхньою компанією, а `supplier` фільтрується лише постачальниками
      цієї компанії.
    - Для адміністраторів усі поля залишаються доступними для вибору.

    Args:
        request: HTTP-запит (використовується для перевірки прав).
        form: Форма замовлення закупівлі.
        user_company: Компанія поточного користувача або `None`, якщо
                      компанію не визначено.

    Returns:
        None. Функція змінює форму за посиланням (side effect).
    """
    if not is_admin_user(request=request):
        if user_company:
            form.fields['company'].queryset = Company.objects.filter(
                pk=user_company.pk,
            )
            form.fields['company'].initial = user_company.pk
            form.fields['company'].disabled = True
            form.fields['supplier'].queryset = user_company.suppliers.all()


def _configure_payment_form_fields(
    request: HttpRequest,
    form: SupplierPaymentForm,
    user_company: Company | None,
    supplier_id: int | None = None,
) -> None:
    """Налаштовує поля форми платежу залежно від прав користувача.

    Args:
        request: HTTP-запит.
        form: Форма платежу.
        user_company: Компанія користувача або None.
        supplier_id: ID постачальника для фільтрації замовлень.
    """
    if not is_admin_user(request=request):
        if user_company:
            form.fields['company'].queryset = Company.objects.filter(
                pk=user_company.pk,
            )
            form.fields['company'].initial = user_company.pk
            form.fields['company'].disabled = True
            form.fields['supplier'].queryset = user_company.suppliers.all()
            po_qs = user_company.purchase_orders.all()
            if supplier_id:
                po_qs = po_qs.filter(supplier_id=supplier_id)
            form.fields['purchase_order'].queryset = po_qs
    else:
        if supplier_id:
            form.fields['purchase_order'].queryset = (
                form.fields['purchase_order'].queryset.filter(
                    supplier_id=supplier_id,
                )
            )
