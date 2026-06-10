import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from company.models import Company

companies_data = [
    {'name': 'АвтоСервіс Плюс',    'email': 'info@autoplus.ua',       'phone': '+380501234561', 'address': 'м. Київ, вул. Автомобільна, 1'},
    {'name': 'АвтоМайстер',        'email': 'info@automeister.ua',    'phone': '+380501234562', 'address': 'м. Львів, вул. Дорожня, 15'},
    {'name': 'Автотехцентр',       'email': 'info@autotech.ua',       'phone': '+380501234563', 'address': 'м. Харків, вул. Шосейна, 42'},
    {'name': 'АвтоДоктор',         'email': 'info@autodoctor.ua',     'phone': '+380501234564', 'address': 'м. Одеса, вул. Ремонтна, 8'},
    {'name': 'АвтоСвіт',           'email': 'info@autosvit.ua',       'phone': '+380501234565', 'address': 'м. Дніпро, вул. Механіків, 23'},
]

for data in companies_data:
    company, created = Company.objects.get_or_create(name=data['name'], defaults=data)
    status = 'Створено' if created else 'Вже існує'
    print(f'{status}: {company.name} (ID={company.pk})')
