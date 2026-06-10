"""Адмін-панель для моделі Client."""

from __future__ import annotations

from django.contrib import admin

from clients.models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Налаштування адмін-панелі для клієнтів."""

    list_display = ('last_name', 'first_name', 'phone', 'email', 'company', 'created_at')
    list_filter = ('company',)
    search_fields = ('last_name', 'first_name', 'phone', 'email')
    ordering = ('last_name', 'first_name')
