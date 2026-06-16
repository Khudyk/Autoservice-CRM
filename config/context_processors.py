"""Контекст-процесори для глобальних змінних шаблонів."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from django.http import HttpRequest

from permissions.utils import get_employee_permissions, has_permission


@dataclass
class NavItem:
    """Елемент навігаційного меню.

    Атрибути:
        label: Текст пункту меню.
        url_name: Ім'я URL-маршруту (для тегу {% url %}).
        url_kwargs: Додаткові kwargs для URL (опціонально).
        icon_class: CSS-клас іконки Bootstrap (bi-*).
        module_codename: Код модуля в системі прав доступу.
    """

    label: str
    url_name: str
    url_kwargs: dict | None = None
    icon_class: str = ''
    module_codename: str = ''

    def get_url(self) -> str:
        """Повертає URL з урахуванням kwargs."""
        from django.urls import reverse
        if self.url_kwargs:
            return reverse(self.url_name, kwargs=self.url_kwargs)
        return reverse(self.url_name)


@dataclass
class NavGroup:
    """Група елементів навігації (випадаюче меню).

    Атрибути:
        label: Текст заголовка групи.
        icon_class: CSS-клас іконки Bootstrap (bi-*).
        children: Список NavItem всередині групи.
    """

    label: str
    icon_class: str = ''
    children: list[NavItem] | None = None


# --- Секції меню ---

BASE_MENU: list[Union[NavItem, NavGroup]] = [
    NavItem(
        label='Головна',
        url_name='index',
        icon_class='bi-house-door',
        module_codename='dashboard',
    ),
    NavItem(
        label='Клієнти',
        url_name='client_list',
        icon_class='bi-person-badge',
        module_codename='clients',
    ),
    NavItem(
        label='Автомобілі',
        url_name='vehicle_list',
        icon_class='bi-car-front',
        module_codename='vehicles',
    ),
    NavItem(
        label='Наряди',
        url_name='workorder_list',
        icon_class='bi-file-earmark-text',
        module_codename='workorders',
    ),
    NavGroup(
        label='Довідники',
        icon_class='bi-book',
        children=[
            NavItem(
                label='Співробітники',
                url_name='employee_list',
                icon_class='bi-people',
                module_codename='employees',
            ),
            NavItem(
                label='Види робіт',
                url_name='worktype_list',
                icon_class='bi-tools',
                module_codename='worktypes',
            ),
            NavItem(
                label='Запчастини',
                url_name='part_list',
                icon_class='bi-box-seam',
                module_codename='parts',
            ),
            NavItem(
                label='Постачальники',
                url_name='supplier_list',
                icon_class='bi-truck',
                module_codename='suppliers',
            ),
        ],
    ),
    NavGroup(
        label='Закупівля / Розрахунки',
        icon_class='bi-cart-plus',
        children=[
            NavItem(
                label='Закупівля',
                url_name='purchase_list',
                icon_class='bi-cart-plus',
                module_codename='purchases',
            ),
            NavItem(
                label='Розрахунки',
                url_name='payment_list',
                icon_class='bi-credit-card',
                module_codename='payments',
            ),
        ],
    ),
]

ADMIN_MENU: list[NavItem] = [
    NavItem(
        label='Адміністрування',
        url_name='admin:index',
        icon_class='bi-gear',
        module_codename='administration',
    ),
    NavItem(
        label='Права доступу',
        url_name='permission_matrix',
        icon_class='bi-shield-lock',
        module_codename='permissions_manage',
    ),
]


def _filter_nav_by_permission(
    items: list[Union[NavItem, NavGroup]],
    employee_permissions: dict[str, set[str]],
) -> list[Union[NavItem, NavGroup]]:
    """Фільтрує список NavItem/NavGroup за правами співробітника.

    Для NavItem — залишає тільки ті, на які співробітник має 'read'.
    Для NavGroup — залишає тільки дочірні пункти з правом 'read',
    а групу ховає, якщо жодного дочірнього пункту не залишилось.
    Якщо прав немає (порожній словник) — показуємо всі (для анонімів).
    """
    if not employee_permissions:
        return items

    result: list[Union[NavItem, NavGroup]] = []
    for item in items:
        if isinstance(item, NavItem):
            if 'read' in employee_permissions.get(item.module_codename, set()):
                result.append(item)
        elif isinstance(item, NavGroup):
            if not item.children:
                continue
            filtered_children: list[NavItem] = [
                child for child in item.children
                if 'read' in employee_permissions.get(child.module_codename, set())
            ]
            if filtered_children:
                item.children = filtered_children
                result.append(item)
    return result


def navigation(request: HttpRequest) -> dict[str, list[Union[NavItem, NavGroup]] | bool]:
    """Формує списки пунктів меню з урахуванням прав.

    Повертає словник з ключами:
    - 'nav_main' — основні пункти меню (відфільтровані за правами)
    - 'nav_admin' — адміністративні пункти
    - 'user_is_manager' — прапорець менеджера
    - 'companies' — список компаній (порожній за замовчуванням)
    - 'selected_company' — вибрана компанія
    - 'can_edit' — чи може користувач редагувати
    """
    user = request.user
    employee_permissions: dict[str, set[str]] = {}
    employee_obj: object | None = None
    current_company: object | None = None

    if user.is_authenticated and hasattr(user, 'employee'):
        employee_obj = user.employee
        current_company = employee_obj.company
        employee_permissions = get_employee_permissions(employee_obj)

    nav_main: list[Union[NavItem, NavGroup]] = _filter_nav_by_permission(BASE_MENU, employee_permissions)
    nav_admin: list[NavItem] = _filter_nav_by_permission(ADMIN_MENU, employee_permissions)

    return {
        'nav_main': nav_main,
        'nav_admin': nav_admin,
        'user_is_manager': False,
        'companies': [],
        'selected_company': current_company,
        'current_company': current_company,
        'current_employee': employee_obj,
        'can_edit': True,
        'user_permissions': employee_permissions,
    }
