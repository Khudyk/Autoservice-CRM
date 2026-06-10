"""Контекст-процесори для глобальних змінних шаблонів."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from django.http import HttpRequest

from accounts.utils import has_salary_report_permission


@dataclass
class NavItem:
    """Елемент навігаційного меню.

    Атрибути:
        label: Текст пункту меню.
        url_name: Ім'я URL-маршруту (для тегу {% url %}).
        icon_class: CSS-клас іконки Bootstrap (bi-*).
        permission_check: Функція, яка приймає HttpRequest і повертає bool.
    """

    label: str
    url_name: str
    icon_class: str = ''
    permission_check: Callable[[HttpRequest], bool] = field(
        default=lambda _: True,
    )


def _is_staff(request: HttpRequest) -> bool:
    """Перевіряє, чи є користувач staff (доступ до Django Admin)."""
    return bool(request.user.is_authenticated and request.user.is_staff)


def _is_superuser(request: HttpRequest) -> bool:
    """Перевіряє, чи є користувач superuser."""
    return bool(request.user.is_authenticated and request.user.is_superuser)


def _is_authenticated(request: HttpRequest) -> bool:
    """Перевіряє, чи аутентифікований користувач."""
    return request.user.is_authenticated


def _is_admin_role(request: HttpRequest) -> bool:
    """Перевіряє, чи має користувач бізнес-роль адміністратора.

    Вважається адміністратором, якщо:
    - Django is_staff або is_superuser, АБО
    - Employee з роллю 'admin' або 'director'
    """
    if not request.user.is_authenticated:
        return False
    if request.user.is_staff or request.user.is_superuser:
        return True
    try:
        employee = request.user.employee  # type: ignore[union-attr]
        return employee.has_any_role({'admin', 'director'})
    except AttributeError:
        return False


def _is_purchase_role(request: HttpRequest) -> bool:
    """Перевіряє, чи має користувач доступ до закупівель.

    Доступ мають:
    - Django is_staff або is_superuser, АБО
    - Employee з роллю 'admin', 'director', 'manager', 'purchaser' або 'storekeeper'
    """
    if not request.user.is_authenticated:
        return False
    if request.user.is_staff or request.user.is_superuser:
        return True
    try:
        employee = request.user.employee  # type: ignore[union-attr]
        return employee.has_any_role({'admin', 'director', 'manager', 'purchaser', 'storekeeper'})
    except AttributeError:
        return False


def _is_salary_role(request: HttpRequest) -> bool:
    """Перевіряє, чи має користувач доступ до зарплатних звітів.

    Доступ мають:
    - Django is_staff або is_superuser, АБО
    - Employee з роллю 'admin', 'director' або 'accountant'
    """
    return has_salary_report_permission(request=request)


def _is_manager(request: HttpRequest) -> bool:
    """Перевіряє, чи має користувач роль менеджера."""
    if not request.user.is_authenticated:
        return False
    try:
        return request.user.employee.has_any_role({'manager'})  # type: ignore[union-attr]
    except AttributeError:
        return False


def _is_not_manager(request: HttpRequest) -> bool:
    """Перевіряє, чи аутентифікований користувач не має ролі manager.

    Staff/superuser завжди проходять (бачать усе).
    """
    if not request.user.is_authenticated:
        return False
    if request.user.is_staff or request.user.is_superuser:
        return True
    try:
        return not request.user.employee.has_any_role({'manager'})  # type: ignore[union-attr]
    except AttributeError:
        return True


def _is_purchase_role_not_manager(request: HttpRequest) -> bool:
    """Перевіряє доступ до закупівель, виключаючи менеджерів.

    Доступ мають:
    - Django is_staff або is_superuser, АБО
    - Employee з роллю 'admin', 'director', 'purchaser' або 'storekeeper'
    - Менеджери — НЕ мають доступу.
    """
    return _is_purchase_role(request) and _is_not_manager(request)


# --- Секції меню ---

BASE_MENU: list[NavItem] = [
    NavItem(
        label='Головна',
        url_name='index',
        icon_class='bi-house-door',
        permission_check=_is_authenticated,
    ),
    NavItem(
        label='Компанії',
        url_name='company_list',
        icon_class='bi-building',
        permission_check=_is_staff,
    ),
    NavItem(
        label='Клієнти',
        url_name='client_list',
        icon_class='bi-person-badge',
        permission_check=_is_authenticated,
    ),
    NavItem(
        label='Автомобілі',
        url_name='vehicle_list',
        icon_class='bi-car-front',
        permission_check=_is_authenticated,
    ),
    NavItem(
        label='Наряди',
        url_name='workorder_list',
        icon_class='bi-file-earmark-text',
        permission_check=_is_authenticated,
    ),
    NavItem(
        label='Співробітники',
        url_name='employee_list',
        icon_class='bi-people',
        permission_check=_is_admin_role,
    ),
    NavItem(
        label='Види робіт',
        url_name='worktype_list',
        icon_class='bi-tools',
        permission_check=_is_authenticated,
    ),
    NavItem(
        label='Постачальники',
        url_name='supplier_list',
        icon_class='bi-truck',
        permission_check=_is_not_manager,
    ),
    NavItem(
        label='Запчастини',
        url_name='part_list',
        icon_class='bi-box-seam',
        permission_check=_is_authenticated,
    ),
    NavItem(
        label='Зарплата механіків',
        url_name='mechanic_salary_report',
        icon_class='bi-calculator',
        permission_check=_is_salary_role,
    ),
    NavItem(
        label='Зарплата менеджерів',
        url_name='manager_salary_report',
        icon_class='bi-calculator',
        permission_check=_is_salary_role,
    ),
    NavItem(
        label='Закупівля',
        url_name='purchase_list',
        icon_class='bi-cart-plus',
        permission_check=_is_purchase_role_not_manager,
    ),
    NavItem(
        label='Розрахунки',
        url_name='payment_list',
        icon_class='bi-credit-card',
        permission_check=_is_purchase_role_not_manager,
    ),
]

ADMIN_MENU: list[NavItem] = [
    NavItem(
        label='Адміністрування',
        url_name='admin:index',
        icon_class='bi-gear',
        permission_check=_is_admin_role,
    ),
]


def navigation(request: HttpRequest) -> dict[str, list[NavItem] | bool]:
    """Формує списки пунктів меню залежно від прав користувача.

    Повертає словник з ключами:
    - 'nav_main' — основні пункти меню (для аутентифікованих)
    - 'nav_admin' — адміністративні пункти (для адмінів)
    - 'user_is_manager' — True, якщо поточний користувач має роль manager
    """
    nav_main: list[NavItem] = [
        item for item in BASE_MENU if item.permission_check(request)
    ]
    nav_admin: list[NavItem] = [
        item for item in ADMIN_MENU if item.permission_check(request)
    ]
    return {
        'nav_main': nav_main,
        'nav_admin': nav_admin,
        'user_is_manager': _is_manager(request),
    }
