"""Утиліти для мульти-тенантної ізоляції даних за компанією."""

from __future__ import annotations

from typing import overload

from django.core.paginator import Paginator, Page
from django.db.models import QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404

from accounts.models import Employee, Role
from company.models import Company


@overload
def _resolve_user(request: HttpRequest, user: None) -> object: ...


@overload
def _resolve_user(request: None, user: object) -> object: ...


def _resolve_user(request: HttpRequest | None, user: object | None) -> object:
    """Повертає user з request або з аргументу user."""
    if request is not None:
        return request.user
    return user


def get_user_company(
    request: HttpRequest | None = None,
    user: object | None = None,
) -> Company | None:
    """Повертає компанію, до якої прив'язаний користувач.

    Приймає або request, або user безпосередньо (для використання у формах).

    Args:
        request: HTTP-запит (опціонально).
        user: Користувач (опціонально, якщо request не передано).

    Returns:
        Компанія користувача або None.
    """
    current_user = _resolve_user(request, user)
    if not current_user or not current_user.is_authenticated:
        return None
    try:
        return current_user.employee.company  # type: ignore[union-attr]
    except AttributeError:
        return None


def is_admin_user(
    request: HttpRequest | None = None,
    user: object | None = None,
) -> bool:
    """Перевіряє, чи є користувач глобальним адміністратором.

    Адміністратор має доступ до всіх компаній (обходить ізоляцію даних).

    Args:
        request: HTTP-запит (опціонально).
        user: Користувач (опціонально, якщо request не передано).

    Returns:
        True, якщо користувач staff або superuser.
    """
    current_user = _resolve_user(request, user)
    if not current_user or not current_user.is_authenticated:
        return False
    return bool(current_user.is_staff or current_user.is_superuser)


def filter_queryset_by_company(
    request: HttpRequest,
    queryset: QuerySet,
    company_field: str = 'company',
) -> QuerySet:
    """Фільтрує QuerySet за компанією поточного користувача.

    Якщо користувач є адміністратором — фільтр не застосовується.
    Для анонімних користувачів повертається порожній QuerySet.

    Args:
        request: HTTP-запит з користувачем.
        queryset: Початковий QuerySet для фільтрації.
        company_field: Ім'я поля компанії в моделі.

    Returns:
        Відфільтрований QuerySet.
    """
    if is_admin_user(request=request):
        return queryset
    company: Company | None = get_user_company(request=request)
    if company is None:
        return queryset.none()
    return queryset.filter(**{company_field: company})


def prepare_list_context(
    request: HttpRequest,
    queryset: QuerySet,
    company_field: str = 'company',
) -> tuple[QuerySet, list[Company], Company | None]:
    """Підготовляє контекст для списків з ізоляцією за компанією.

    Об'єднує логіку фільтрації, яка дублювалася в кожному list-view:
    - Адміністратори бачать усі записи з можливістю фільтру за `?company=<pk>`.
    - Звичайні користувачі бачать лише записи своєї компанії.

    Args:
        request: HTTP-запит.
        queryset: Початковий QuerySet (бажано вже з `select_related('company')`).
        company_field: Ім'я поля компанії в моделі.

    Returns:
        Кортеж (відфільтрований_queryset, список_компаній, обрана_компанія).
    """
    if is_admin_user(request=request):
        company_id: str | None = request.GET.get('company')
        selected_company: Company | None = None
        if company_id:
            try:
                pk: int = int(company_id)
                selected_company = get_object_or_404(Company, pk=pk)
                queryset = queryset.filter(**{company_field: pk})
            except (ValueError, TypeError):
                selected_company = None
        companies: list[Company] = list(Company.objects.all().order_by('name'))
    else:
        user_company: Company | None = get_user_company(request=request)
        if user_company:
            queryset = queryset.filter(**{company_field: user_company})
            companies = [user_company]
            selected_company = user_company
        else:
            queryset = queryset.none()
            companies = []
            selected_company = None

    return queryset, companies, selected_company


# Ролі, які мають право редагувати довідники (види робіт, постачальники,
# запчастини) та рядки робіт/запчастин у заказ-нарядах.
# Менеджери та механіки можуть переглядати, але не можуть змінювати.
_CATALOG_EDIT_ALLOWED_ROLES: frozenset[str] = frozenset({
    'director',
    'admin',
})

# Ролі, які мають право створювати/редагувати/видаляти клієнтів.
# Менеджер може вести клієнтську базу (створювати клієнтів та прив'язувати
# їх до автомобілів). Механіки — лише перегляд.
_CLIENT_EDIT_ALLOWED_ROLES: frozenset[str] = frozenset({
    'director',
    'admin',
    'manager',
})


def has_catalog_edit_permission(
    request: HttpRequest | None = None,
    user: object | None = None,
) -> bool:
    """Перевіряє, чи має користувач право редагувати довідкові дані.

    Застосовується для:
    - Видів робіт (WorkType)
    - Постачальників (Supplier)
    - Запчастин (Part)
    - Рядків робіт та запчастин у заказ-нарядах (WorkOrderService, WorkOrderPart)

    Редагувати дозволено лише:
    - Django staff/superuser
    - Співробітникам з ролями «Директор» або «Адміністратор»

    Args:
        request: HTTP-запит (опціонально).
        user: Користувач (опціонально, якщо request не передано).

    Returns:
        True, якщо користувач може редагувати довідкові дані.
    """
    current_user = _resolve_user(request, user)
    if not current_user or not current_user.is_authenticated:
        return False
    # Django staff/superuser мають повний доступ
    if current_user.is_staff or current_user.is_superuser:
        return True
    # Перевіряємо бізнес-роль співробітника
    try:
        employee: Employee = current_user.employee  # type: ignore[union-attr]
        return employee.has_any_role(_CATALOG_EDIT_ALLOWED_ROLES)
    except AttributeError:
        return False


def has_client_edit_permission(
    request: HttpRequest | None = None,
    user: object | None = None,
) -> bool:
    """Перевіряє, чи має користувач право створювати/редагувати/видаляти клієнтів.

    Дозволено:
    - Django staff/superuser
    - Співробітникам з ролями «Директор», «Адміністратор» або «Менеджер»

    Args:
        request: HTTP-запит (опціонально).
        user: Користувач (опціонально, якщо request не передано).

    Returns:
        True, якщо користувач може редагувати клієнтів.
    """
    current_user = _resolve_user(request, user)
    if not current_user or not current_user.is_authenticated:
        return False
    if current_user.is_staff or current_user.is_superuser:
        return True
    try:
        employee: Employee = current_user.employee  # type: ignore[union-attr]
        return employee.has_any_role(_CLIENT_EDIT_ALLOWED_ROLES)
    except AttributeError:
        return False


# Ролі, які мають право створювати/редагувати/видаляти автомобілі.
# Менеджери працюють із заказ-нарядами, тому мають змінювати власника
# автомобіля. Механіки — лише перегляд.
_VEHICLE_EDIT_ALLOWED_ROLES: frozenset[str] = frozenset({
    'director',
    'admin',
    'manager',
})


def has_vehicle_edit_permission(
    request: HttpRequest | None = None,
    user: object | None = None,
) -> bool:
    """Перевіряє, чи має користувач право створювати/редагувати/видаляти автомобілі.

    Дозволено:
    - Django staff/superuser
    - Співробітникам з ролями «Директор», «Адміністратор» або «Менеджер»

    Args:
        request: HTTP-запит (опціонально).
        user: Користувач (опціонально, якщо request не передано).

    Returns:
        True, якщо користувач може редагувати автомобілі.
    """
    current_user = _resolve_user(request, user)
    if not current_user or not current_user.is_authenticated:
        return False
    if current_user.is_staff or current_user.is_superuser:
        return True
    try:
        employee: Employee = current_user.employee  # type: ignore[union-attr]
        return employee.has_any_role(_VEHICLE_EDIT_ALLOWED_ROLES)
    except AttributeError:
        return False


# Ролі, які мають право працювати із закупівлями.
# Закупівельники, менеджери, адміністратори та директори можуть створювати
# та проводити закупівлі. Складовщики мають доступ для оприбуткування.
_PURCHASE_ALLOWED_ROLES: frozenset[str] = frozenset({
    'director',
    'admin',
    'manager',
    'purchaser',
    'storekeeper',
})

# Ролі, які мають право створювати/редагувати/видаляти закупівлі.
# Складовщики можуть лише переглядати та оприбутковувати товар.
_PURCHASE_EDIT_ALLOWED_ROLES: frozenset[str] = frozenset({
    'director',
    'admin',
    'manager',
    'purchaser',
})


def has_purchase_permission(
    request: HttpRequest | None = None,
    user: object | None = None,
) -> bool:
    """Перевіряє, чи має користувач право працювати із закупівлями.

    Доступ дозволено:
    - Django staff/superuser
    - Співробітникам з ролями «Директор», «Адміністратор», «Менеджер»,
      «Закупівельник» або «Складовщик»

    Args:
        request: HTTP-запит (опціонально).
        user: Користувач (опціонально, якщо request не передано).

    Returns:
        True, якщо користувач може переглядати закупівлі.
    """
    current_user = _resolve_user(request, user)
    if not current_user or not current_user.is_authenticated:
        return False
    if current_user.is_staff or current_user.is_superuser:
        return True
    try:
        employee: Employee = current_user.employee  # type: ignore[union-attr]
        return employee.has_any_role(_PURCHASE_ALLOWED_ROLES)
    except AttributeError:
        return False


# Ролі, які мають право редагувати продажну ціну запчастин.
# Доступ ширший ніж has_catalog_edit_permission — додатково включає
# менеджерів та закупівельників, які бачать закупівельні ціни.
_PRICE_EDIT_ALLOWED_ROLES: frozenset[str] = frozenset({
    'director',
    'admin',
    'manager',
    'purchaser',
})


def has_price_edit_permission(
    request: HttpRequest | None = None,
    user: object | None = None,
) -> bool:
    """Перевіряє, чи має користувач право редагувати продажну ціну запчастини.

    Відрізняється від `has_catalog_edit_permission` тим, що додатково
    включає ролі «Менеджер» (manager) та «Закупівельник» (purchaser),
    які мають доступ до цін, але не редагують довідкові дані.

    Доступ дозволено:
    - Django staff/superuser
    - Співробітникам з ролями «Директор», «Адміністратор»,
      «Менеджер» або «Закупівельник»

    Args:
        request: HTTP-запит (опціонально).
        user: Користувач (опціонально, якщо request не передано).

    Returns:
        True, якщо користувач може редагувати продажну ціну.
    """
    current_user = _resolve_user(request, user)
    if not current_user or not current_user.is_authenticated:
        return False
    if current_user.is_staff or current_user.is_superuser:
        return True
    try:
        employee: Employee = current_user.employee  # type: ignore[union-attr]
        return employee.has_any_role(_PRICE_EDIT_ALLOWED_ROLES)
    except AttributeError:
        return False


def has_purchase_edit_permission(
    request: HttpRequest | None = None,
    user: object | None = None,
) -> bool:
    """Перевіряє, чи має користувач право створювати/редагувати закупівлі.

    Відрізняється від `has_purchase_permission` тим, що **виключає**
    роль «Складовщик» (storekeeper) — складовщики можуть лише
    переглядати та оприбутковувати товар, але не створювати,
    редагувати, відправляти, скасовувати чи видаляти замовлення.

    Доступ дозволено:
    - Django staff/superuser
    - Співробітникам з ролями «Директор», «Адміністратор»,
      «Менеджер» або «Закупівельник»

    Args:
        request: HTTP-запит (опціонально).
        user: Користувач (опціонально, якщо request не передано).

    Returns:
        True, якщо користувач може редагувати закупівлі.
    """
    current_user = _resolve_user(request, user)
    if not current_user or not current_user.is_authenticated:
        return False
    if current_user.is_staff or current_user.is_superuser:
        return True
    try:
        employee: Employee = current_user.employee  # type: ignore[union-attr]
        return employee.has_any_role(_PURCHASE_EDIT_ALLOWED_ROLES)
    except AttributeError:
        return False


# Ролі, які мають право працювати із заказ-нарядами (створення, редагування,
# видалення). Менеджери, адміністратори та директори можуть повністю
# керувати нарядами. Інші ролі (майстри, бухгалтери тощо) — лише перегляд.
_WORKORDER_ALLOWED_ROLES: frozenset[str] = frozenset({
    'director',
    'admin',
    'manager',
})

# Ролі, які мають право переглядати зарплатні звіти (механіків і менеджерів).
_SALARY_ALLOWED_ROLES: frozenset[str] = frozenset({
    'director',
    'admin',
    'accountant',
})


def has_workorder_permission(
    request: HttpRequest | None = None,
    user: object | None = None,
) -> bool:
    """Перевіряє, чи має користувач право працювати із заказ-нарядами.

    Відрізняється від `has_catalog_edit_permission` тим, що додатково
    включає роль «Менеджер» (manager), яка має право створювати,
    редагувати та видаляти заказ-наряди, але не має права змінювати
    довідкові дані (види робіт, постачальників, запчастини).

    Доступ дозволено:
    - Django staff/superuser
    - Співробітникам з ролями «Директор», «Адміністратор» або «Менеджер»

    Args:
        request: HTTP-запит (опціонально).
        user: Користувач (опціонально, якщо request не передано).

    Returns:
        True, якщо користувач може працювати із заказ-нарядами.
    """
    current_user = _resolve_user(request, user)
    if not current_user or not current_user.is_authenticated:
        return False
    if current_user.is_staff or current_user.is_superuser:
        return True
    try:
        employee: Employee = current_user.employee  # type: ignore[union-attr]
        return employee.has_any_role(_WORKORDER_ALLOWED_ROLES)
    except AttributeError:
        return False


def has_salary_report_permission(
    request: HttpRequest | None = None,
    user: object | None = None,
) -> bool:
    """Перевіряє, чи має користувач право переглядати зарплатні звіти.

    Доступ дозволено:
    - Django staff/superuser
    - Співробітникам з ролями «Директор», «Адміністратор» або «Бухгалтер»

    Args:
        request: HTTP-запит (опціонально).
        user: Користувач (опціонально, якщо request не передано).

    Returns:
        True, якщо користувач може переглядати звіти.
    """
    current_user = _resolve_user(request, user)
    if not current_user or not current_user.is_authenticated:
        return False
    if current_user.is_staff or current_user.is_superuser:
        return True
    try:
        employee: Employee = current_user.employee  # type: ignore[union-attr]
        return employee.has_any_role(_SALARY_ALLOWED_ROLES)
    except AttributeError:
        return False


def paginate_queryset(
    request: HttpRequest,
    queryset: QuerySet,
    per_page: int = 25,
) -> Page:
    """Розбиває QuerySet на сторінки та повертає об'єкт сторінки.

    Читає номер сторінки з `request.GET.get('page')`.
    Якщо параметр відсутній або некоректний — повертає першу сторінку.

    Args:
        request: HTTP-запит з можливим параметром `?page=`.
        queryset: QuerySet для пагінації.
        per_page: Кількість записів на сторінці (за замовчуванням 25).

    Returns:
        Page: Об'єкт сторінки з ітерабельними записами.
    """
    paginator: Paginator = Paginator(queryset, per_page)
    page_number: str | None = request.GET.get('page')
    page_obj: Page = paginator.get_page(page_number)
    return page_obj
