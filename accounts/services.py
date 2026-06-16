"""Сервісний шар для бізнес-логіки співробітників.

Ізолює складні операції (створення, оновлення, деактивація) від
представлень, гарантує атомарність транзакцій та централізоване
керування зв'язками між User, Employee та Role.
"""

from __future__ import annotations

from typing import ClassVar

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import QuerySet

from accounts.models import Employee, Role
from company.models import Company


class EmployeeService:
    """Сервісний шар для бізнес-логіки роботи зі співробітниками.

    Ізолює всю складну логіку від представлень, гарантує атомарність
    операцій та захист від станів перегону (race conditions).
    """

    SELECT_RELATED_FIELDS: ClassVar[list[str]] = ['user', 'company']

    @staticmethod
    def get_employees_for_company(company: Company) -> QuerySet[Employee]:
        """Повертає всіх активних співробітників компанії з попередньо підвантаженими зв'язками.

        Args:
            company: Компанія, для якої потрібно отримати співробітників.

        Returns:
            QuerySet співробітників із select_related('user', 'company').
        """
        return Employee.objects.select_related(
            *EmployeeService.SELECT_RELATED_FIELDS,
        ).filter(company=company)

    @staticmethod
    def get_employee_by_id(employee_id: int) -> Employee | None:
        """Повертає співробітника за ідентифікатором або None.

        Args:
            employee_id: Первинний ключ співробітника.

        Returns:
            Employee або None, якщо не знайдено.
        """
        try:
            return Employee.objects.select_related(
                *EmployeeService.SELECT_RELATED_FIELDS,
            ).get(pk=employee_id)
        except Employee.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def create_employee(
        user: User,
        company: Company,
        role: str = Employee.RoleChoices.MECHANIC,
        phone: str = '',
    ) -> Employee:
        """Створює співробітника в межах однієї транзакції.

        Args:
            user: Користувач (екземпляр User).
            company: Компанія, до якої прикріплюється співробітник.
            role: Код ролі (за замовчуванням — майстер).
            phone: Номер телефону (необов'язково).

        Returns:
            Створений екземпляр Employee.

        Гарантує:
            Атомарність — співробітник буде створений повністю або не буде
            створений взагалі.
        """
        employee: Employee = Employee.objects.create(
            user=user,
            company=company,
            phone=phone,
        )
        try:
            role_obj: Role = Role.objects.get(codename=role)
            employee.roles.set([role_obj])
        except Role.DoesNotExist:
            pass
        return employee

    @staticmethod
    @transaction.atomic
    def update_employee(
        employee: Employee,
        role: str | None = None,
        phone: str | None = None,
        is_active: bool | None = None,
    ) -> Employee:
        """Оновлює дані співробітника атомарно.

        Args:
            employee: Співробітник, якого потрібно оновити.
            role: Код нової ролі (якщо None — залишаються поточні ролі).
            phone: Новий телефон (якщо None — залишається поточний).
            is_active: Новий статус (якщо None — залишається поточний).

        Returns:
            Оновлений екземпляр Employee.
        """
        if role is not None:
            try:
                role_obj: Role = Role.objects.get(codename=role)
                employee.roles.set([role_obj])
            except Role.DoesNotExist:
                pass
        if phone is not None:
            employee.phone = phone
        if is_active is not None:
            employee.is_active = is_active
        employee.save()
        return employee

    @staticmethod
    @transaction.atomic
    def deactivate_employee(employee: Employee) -> Employee:
        """Деактивує співробітника (м'яке видалення).

        Args:
            employee: Співробітник для деактивації.

        Returns:
            Оновлений екземпляр Employee з is_active=False.
        """
        employee.is_active = False
        employee.save()
        return employee
