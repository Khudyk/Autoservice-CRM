"""Моделі для керування правами доступу до сторінок.

Схема:
- Module — сторінка/ресурс системи (наприклад 'companies', 'workorders').
- EmployeePermission — індивідуальні права співробітника на модуль.
"""

from __future__ import annotations

from django.db import models


class Module(models.Model):
    """Модуль (сторінка) системи, на яку призначаються права."""

    codename = models.CharField(
        'Код',
        max_length=50,
        unique=True,
        help_text='Унікальний ідентифікатор модуля (companies, workorders, …)',
    )
    name = models.CharField(
        'Назва',
        max_length=100,
        help_text='Людиночитана назва модуля (Компанії, Наряди, …)',
    )
    description = models.TextField(
        'Опис',
        blank=True,
        help_text='Необов\'язковий опис модуля',
    )

    class Meta:
        verbose_name = 'Модуль'
        verbose_name_plural = 'Модулі'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class EmployeePermission(models.Model):
    """Індивідуальні права співробітника на модуль.

    Якщо запис існує — він повністю визначає доступ співробітника
    до модуля (рольові права не враховуються).
    Якщо запису немає — доступ закрито.
    """

    employee = models.ForeignKey(
        'accounts.Employee',
        on_delete=models.CASCADE,
        related_name='permissions',
        verbose_name='Співробітник',
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='employee_permissions',
        verbose_name='Модуль',
    )
    can_read = models.BooleanField('Читання', default=False)
    can_create = models.BooleanField('Створення', default=False)
    can_edit = models.BooleanField('Редагування', default=False)
    can_delete = models.BooleanField('Видалення', default=False)

    class Meta:
        verbose_name = 'Право співробітника'
        verbose_name_plural = 'Права співробітників'
        unique_together = ['employee', 'module']

    def __str__(self) -> str:
        actions = []
        if self.can_read:
            actions.append('читати')
        if self.can_create:
            actions.append('створювати')
        if self.can_edit:
            actions.append('редагувати')
        if self.can_delete:
            actions.append('видаляти')
        return f'{self.employee} → {self.module.name} ({", ".join(actions) or "немає"})'
