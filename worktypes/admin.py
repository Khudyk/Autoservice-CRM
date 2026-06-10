"""Реєстрація моделей в адмін-панелі Django."""

from __future__ import annotations

from django.contrib import admin

from worktypes.models import WorkType


@admin.register(WorkType)
class WorkTypeAdmin(admin.ModelAdmin):
    """Адмін-панель для моделі WorkType."""

    list_display = [
        'name', 'category', 'is_active', 'company',
    ]
    list_filter = ['category', 'is_active', 'company']
    search_fields = ['name', 'description']
