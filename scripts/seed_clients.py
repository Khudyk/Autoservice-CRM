"""Seed 10 test clients with separate first_name / last_name."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from clients.models import Client
from company.models import Company

company = Company.objects.first()
if not company:
    print('ERROR: No company found. Run seed scripts first.')
    exit(1)

clients_data = [
    {'first_name': 'Петро', 'last_name': 'Петренко', 'phone': '+380501111111', 'email': 'petro@email.com', 'notes': 'Постійний клієнт, авто Volkswagen'},
    {'first_name': 'Марія', 'last_name': 'Іваненко', 'phone': '+380501111112', 'email': 'maria@email.com', 'notes': ''},
    {'first_name': 'Іван', 'last_name': 'Сидоренко', 'phone': '+380501111113', 'email': 'ivan.s@email.com', 'notes': 'Корпоративний клієнт'},
    {'first_name': 'Олена', 'last_name': 'Коваль', 'phone': '+380501111114', 'email': 'koval@email.com', 'notes': ''},
    {'first_name': 'ТОВ "АвтоТрейд"', 'last_name': '', 'phone': '+380441111115', 'email': 'info@avtotrade.ua', 'notes': 'Юридична особа, парк з 5 авто'},
    {'first_name': 'Сергій', 'last_name': 'Бондар', 'phone': '+380501111116', 'email': 'bondar@email.com', 'notes': 'Рекомендував Петренко'},
    {'first_name': 'Наталія', 'last_name': 'Шевченко', 'phone': '+380501111117', 'email': 'shevchenko@email.com', 'notes': ''},
    {'first_name': 'Андрій', 'last_name': 'Ткаченко', 'phone': '+380501111118', 'email': 'andrij@email.com', 'notes': 'Власник BMW'},
    {'first_name': 'ФОП "Коваленко С.І."', 'last_name': '', 'phone': '+380441111119', 'email': 'kovalenko@fop.ua', 'notes': 'Таксі-парк'},
    {'first_name': 'Оксана', 'last_name': 'Романюк', 'phone': '+380501111120', 'email': 'oksana@email.com', 'notes': ''},
]

created = 0
for data in clients_data:
    _, was_created = Client.objects.get_or_create(
        first_name=data['first_name'],
        phone=data['phone'],
        defaults={**data, 'company': company},
    )
    if was_created:
        created += 1
        full = f'{data["last_name"]} {data["first_name"]}'.strip()
        print(f'  [OK] {full} ({data["phone"]})')
    else:
        print(f'  [SKIP] {data["first_name"]} — вже існує')

print(f'\nСтворено {created} клієнтів. Всього в БД: {Client.objects.count()}')
