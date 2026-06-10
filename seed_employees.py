"""Створення співробітників для першої компанії."""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Employee, Role
from company.models import Company

company = Company.objects.get(pk=1)
print(f'Компанія: {company.name} (ID={company.pk})')

employees_data = [
    {
        'username': 'director1', 'password': 'pass12345',
        'first_name': 'Олег', 'last_name': 'Іванчук',
        'role_codename': 'director', 'phone': '+380671111111',
    },
    {
        'username': 'manager1', 'password': 'pass12345',
        'first_name': 'Марія', 'last_name': 'Петренко',
        'role_codename': 'manager', 'phone': '+380671111112',
    },
    {
        'username': 'mechanic1', 'password': 'pass12345',
        'first_name': 'Іван', 'last_name': 'Коваль',
        'role_codename': 'mechanic', 'phone': '+380671111113',
        'parts_sale_percent': 5.00, 'labor_percent': 10.00,
    },
    {
        'username': 'mechanic2', 'password': 'pass12345',
        'first_name': 'Петро', 'last_name': 'Шевченко',
        'role_codename': 'mechanic', 'phone': '+380671111114',
        'parts_sale_percent': 5.00, 'labor_percent': 10.00,
    },
    {
        'username': 'accountant1', 'password': 'pass12345',
        'first_name': 'Оксана', 'last_name': 'Бондар',
        'role_codename': 'accountant', 'phone': '+380671111115',
    },
    {
        'username': 'admin1', 'password': 'pass12345',
        'first_name': 'Андрій', 'last_name': 'Мельник',
        'role_codename': 'admin', 'phone': '+380671111116',
    },
    {
        'username': 'purchaser1', 'password': 'pass12345',
        'first_name': 'Дмитро', 'last_name': 'Лисенко',
        'role_codename': 'purchaser', 'phone': '+380671111117',
    },
    {
        'username': 'storekeeper1', 'password': 'pass12345',
        'first_name': 'Василь', 'last_name': 'Кравчук',
        'role_codename': 'storekeeper', 'phone': '+380671111118',
    },
]

for data in employees_data:
    user, user_created = User.objects.get_or_create(
        username=data['username'],
        defaults={
            'first_name': data['first_name'],
            'last_name': data['last_name'],
        },
    )
    if user_created:
        user.set_password(data['password'])
        user.save()
        print(f'  [OK] User створено: {user.username}')
    else:
        print(f'  [WARN] User вже існує: {user.username}')

    emp, emp_created = Employee.objects.get_or_create(
        user=user,
        company=company,
        defaults={
            'phone': data['phone'],
            'parts_sale_percent': data.get('parts_sale_percent', 0.00),
            'labor_percent': data.get('labor_percent', 0.00),
        },
    )
    if emp_created:
        try:
            role_obj = Role.objects.get(codename=data['role_codename'])
            emp.roles.add(role_obj)
        except Role.DoesNotExist:
            print(f'  [WARN] Роль "{data["role_codename"]}" не знайдена в БД')
        print(f'  [OK] Employee створено: {user.get_full_name()} - {data["role_codename"]}')
    else:
        print(f'  [WARN] Employee вже існує: {user.get_full_name()}')

total = Employee.objects.filter(company=company).count()
print(f'\nГотово! Створено {total} співробітників для "{company.name}".')
