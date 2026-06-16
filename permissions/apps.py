"""Конфігурація додатку permissions."""

from __future__ import annotations

from django.apps import AppConfig


class PermissionsConfig(AppConfig):
    """Налаштування додатку прав доступу."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'permissions'
    verbose_name = 'Права доступу'
