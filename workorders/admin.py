"""Адмін-панель для заказ-нарядів."""

from __future__ import annotations

from django.contrib import admin

from workorders.models import WorkOrder, WorkOrderService, WorkOrderPart


class WorkOrderServiceInline(admin.TabularInline):
    """Інлайн редагування робіт у наряді."""
    model = WorkOrderService
    extra = 1
    fields = ('work_type', 'quantity', 'unit_price', 'employee', 'description')


class WorkOrderPartInline(admin.TabularInline):
    """Інлайн редагування запчастин у наряді."""
    model = WorkOrderPart
    extra = 1
    fields = ('part', 'quantity', 'unit_price')


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    """Адмін-панель для заказ-нарядів."""
    list_display = ['pk', 'vehicle', 'company', 'status', 'total_amount', 'created_at']
    list_filter = ['status', 'company']
    search_fields = ['vehicle__vin_code', 'vehicle__brand', 'vehicle__model', 'notes']
    inlines = [WorkOrderServiceInline, WorkOrderPartInline]
    readonly_fields = ['created_at', 'updated_at']
