"""Адмін-інтерфейс для керування правами."""

from __future__ import annotations

from django.contrib import admin

from permissions.models import EmployeePermission, Module


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    """Адмінка для модулів."""

    list_display = ['name', 'codename', 'description']
    search_fields = ['name', 'codename']


@admin.register(EmployeePermission)
class EmployeePermissionAdmin(admin.ModelAdmin):
    """Адмінка для прав співробітників."""

    list_display = ['employee', 'module', 'can_read', 'can_create', 'can_edit', 'can_delete']
    list_filter = ['can_read', 'can_create', 'can_edit', 'can_delete']
    search_fields = ['employee__user__username', 'module__name']
