"""Реєстрація моделей в адмін-панелі Django."""

from __future__ import annotations

from django.contrib import admin

from vehicles.models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    """Адмін-панель для моделі Vehicle."""

    list_display = [
        'vin_code', 'brand', 'model', 'year',
        'engine_type', 'engine_displacement', 'company',
    ]
    list_filter = ['engine_type', 'brand', 'company']
    search_fields = ['vin_code', 'brand', 'model']
