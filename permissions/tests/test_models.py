"""Тести моделей додатку permissions (Module, EmployeePermission)."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from accounts.models import Employee
from permissions.models import EmployeePermission, Module


class TestModuleModel:
    """Тести моделі Module."""

    def test_module_str_returns_name(self, module_parts: Module) -> None:
        """__str__ повертає назву модуля."""
        assert str(module_parts) == 'Запчастини'

    def test_module_codename_unique(self, db: None) -> None:
        """Код модуля має бути унікальним."""
        Module.objects.create(codename='test', name='Тест')
        with pytest.raises(IntegrityError):
            Module.objects.create(codename='test', name='Інший')

    def test_module_ordering(self, db: None) -> None:
        """Модулі сортуються за назвою."""
        Module.objects.create(codename='z', name='Яблуко')
        Module.objects.create(codename='a', name='Абрикос')
        modules = list(Module.objects.all())
        names = [m.name for m in modules]
        assert names == sorted(names)


class TestEmployeePermissionModel:
    """Тести моделі EmployeePermission."""

    def test_create_permission(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Створення права з can_read=True."""
        perm = EmployeePermission.objects.create(
            employee=employee,
            module=module_parts,
            can_read=True,
        )
        assert perm.can_read is True
        assert perm.can_create is False
        assert perm.can_edit is False
        assert perm.can_delete is False

    def test_unique_employee_module(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Не можна створити два права для одного employee+module."""
        EmployeePermission.objects.create(
            employee=employee,
            module=module_parts,
            can_read=True,
        )
        with pytest.raises(IntegrityError):
            EmployeePermission.objects.create(
                employee=employee,
                module=module_parts,
                can_create=True,
            )

    def test_str_representation(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """__str__ показує співробітника, модуль і дії."""
        perm = EmployeePermission.objects.create(
            employee=employee,
            module=module_parts,
            can_read=True,
            can_edit=True,
        )
        result = str(perm)
        assert employee.user.get_full_name() in result
        assert module_parts.name in result
        assert 'читати' in result
        assert 'редагувати' in result

    def test_str_no_permissions(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """__str__ показує 'немає' коли всі права False."""
        perm = EmployeePermission.objects.create(
            employee=employee,
            module=module_parts,
        )
        assert 'немає' in str(perm)

    def test_cascade_delete_employee(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Видалення співробітника видаляє його права."""
        EmployeePermission.objects.create(
            employee=employee,
            module=module_parts,
            can_read=True,
        )
        pk = employee.pk
        employee.delete()
        assert EmployeePermission.objects.filter(employee_id=pk).count() == 0

    def test_cascade_delete_module(
        self,
        employee: Employee,
        module_parts: Module,
    ) -> None:
        """Видалення модуля видаляє пов'язані права."""
        module_pk = module_parts.pk
        EmployeePermission.objects.create(
            employee=employee,
            module=module_parts,
            can_read=True,
        )
        module_parts.delete()
        assert EmployeePermission.objects.filter(module_id=module_pk).count() == 0
