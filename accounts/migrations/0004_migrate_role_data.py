"""Міграція даних: переносить значення старого поля `role` у нову M2M `roles`.

Створює записи Role згідно зі списком констант та для кожного
співробітника, у якого заповнене поле `role`, додає відповідний
зв'язок у таблицю `accounts_employee_roles`.
"""

from __future__ import annotations

from django.db import migrations


ROLES_MAP: dict[str, str] = {
    'director': 'Директор',
    'manager': 'Менеджер',
    'mechanic': 'Майстер',
    'accountant': 'Бухгалтер',
    'admin': 'Адміністратор',
    'purchaser': 'Закупівельник',
    'storekeeper': 'Складовщик',
}


def migrate_roles(apps, schema_editor) -> None:
    """Створює Role-записи та переносить старі значення role у M2M."""
    Role = apps.get_model('accounts', 'Role')
    Employee = apps.get_model('accounts', 'Employee')

    # Створюємо всі ролі
    role_instances: dict[str, object] = {}
    for codename, name in ROLES_MAP.items():
        role, _ = Role.objects.get_or_create(codename=codename, defaults={'name': name})
        role_instances[codename] = role

    # Переносимо дані з role -> roles
    through_model = Employee.roles.through
    for emp in Employee.objects.exclude(role=''):
        codename: str = emp.role
        if codename in role_instances:
            through_model.objects.get_or_create(
                employee_id=emp.pk,
                role_id=role_instances[codename].pk,
            )


def reverse_migrate_roles(apps, schema_editor) -> None:
    """Зворотна міграція: видаляє всі Role та зв'язки.

    Не намагається відновити старі значення role, оскільки
    це поле вже може бути видалене в наступній міграції.
    """
    Role = apps.get_model('accounts', 'Role')
    Role.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_role_alter_employee_role_employee_roles'),
    ]

    operations = [
        migrations.RunPython(migrate_roles, reverse_migrate_roles),
    ]
