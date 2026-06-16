"""Додаткові template-фільтри для модуля permissions."""

from __future__ import annotations

from typing import Any

from django import template

register = template.Library()


@register.filter
def dict_key(d: dict[Any, Any], key: Any) -> Any:
    """Повертає значення словника за ключем або порожній dict/set.

    Використання: ``{{ mydict|dict_key:key_var }}``
    """
    return d.get(key, {})
