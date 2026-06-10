"""Команда для імітації роботи автосервісу за 3 місяці.

Створює реалістичний набір даних: співробітників, клієнтів,
автомобілів, запчастин, закупівель та заказ-нарядів.

Приклад:
    python manage.py simulate_work
    python manage.py simulate_work --force  # очистити старі дані
"""

from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.db.models import F
from django.utils import timezone as tz

from accounts.models import Employee, Role
from clients.models import Client
from company.models import Company
from parts.models import Part, PartLot
from parts.services import PartService
from purchases.models import PurchaseOrder, PurchaseOrderItem, SupplierPayment
from suppliers.models import Supplier
from vehicles.models import Vehicle
from workorders.models import WorkOrder, WorkOrderPart, WorkOrderService
from worktypes.models import WorkType

# ======================================================================
# ДАНІ ДЛЯ ІМІТАЦІЇ
# ======================================================================

EMPLOYEES_DATA: list[dict[str, Any]] = [
    {'username': 'admin', 'first_name': 'Тетяна', 'last_name': 'Коваль', 'roles': ['admin'], 'phone': '+380671112200', 'parts_sale_percent': 0, 'labor_percent': 0},
    {'username': 'director', 'first_name': 'Олександр', 'last_name': 'Мельник', 'roles': ['director'], 'phone': '+380671112201', 'parts_sale_percent': 2, 'labor_percent': 5},
    {'username': 'manager', 'first_name': 'Наталія', 'last_name': 'Шевченко', 'roles': ['manager'], 'phone': '+380671112202', 'parts_sale_percent': 1.5, 'labor_percent': 3},
    {'username': 'mechanic1', 'first_name': 'Іван', 'last_name': 'Петренко', 'roles': ['mechanic'], 'phone': '+380671112203', 'parts_sale_percent': 0.5, 'labor_percent': 40},
    {'username': 'mechanic2', 'first_name': 'Олег', 'last_name': 'Ковальчук', 'roles': ['mechanic'], 'phone': '+380671112204', 'parts_sale_percent': 0.5, 'labor_percent': 35},
    {'username': 'mechanic3', 'first_name': 'Михайло', 'last_name': 'Бондаренко', 'roles': ['mechanic'], 'phone': '+380671112205', 'parts_sale_percent': 0.5, 'labor_percent': 38},
    {'username': 'mechanic4', 'first_name': 'Андрій', 'last_name': 'Кравченко', 'roles': ['mechanic'], 'phone': '+380671112206', 'parts_sale_percent': 0.5, 'labor_percent': 32},
    {'username': 'mechanic5', 'first_name': 'Сергій', 'last_name': 'Олійник', 'roles': ['mechanic'], 'phone': '+380671112207', 'parts_sale_percent': 0.5, 'labor_percent': 36},
    {'username': 'accountant', 'first_name': 'Олена', 'last_name': 'Савченко', 'roles': ['accountant'], 'phone': '+380671112208', 'parts_sale_percent': 0, 'labor_percent': 0},
    {'username': 'storekeeper', 'first_name': 'Дмитро', 'last_name': 'Ткаченко', 'roles': ['storekeeper'], 'phone': '+380671112209', 'parts_sale_percent': 0, 'labor_percent': 0},
    {'username': 'purchaser', 'first_name': 'Віталій', 'last_name': 'Грищенко', 'roles': ['purchaser'], 'phone': '+380671112210', 'parts_sale_percent': 0, 'labor_percent': 0},
]

CLIENTS_DATA: list[dict[str, str]] = [
    {'first_name': 'Петро', 'last_name': 'Іваненко', 'phone': '+380501234501'},
    {'first_name': 'Марія', 'last_name': 'Коваленко', 'phone': '+380501234502'},
    {'first_name': 'Василь', 'last_name': 'Бойко', 'phone': '+380501234503'},
    {'first_name': 'Оксана', 'last_name': 'Ткаченко', 'phone': '+380501234504'},
    {'first_name': 'Ігор', 'last_name': 'Мороз', 'phone': '+380501234505'},
    {'first_name': 'Юлія', 'last_name': 'Лисенко', 'phone': '+380501234506'},
    {'first_name': 'Сергій', 'last_name': 'Гончар', 'phone': '+380501234507'},
    {'first_name': 'Анна', 'last_name': 'Поліщук', 'phone': '+380501234508'},
    {'first_name': 'Микола', 'last_name': 'Романенко', 'phone': '+380501234509'},
    {'first_name': 'Ольга', 'last_name': 'Савчук', 'phone': '+380501234510'},
    {'first_name': 'Дмитро', 'last_name': 'Кравчук', 'phone': '+380501234511'},
    {'first_name': 'Катерина', 'last_name': 'Павленко', 'phone': '+380501234512'},
    {'first_name': 'Андрій', 'last_name': 'Демченко', 'phone': '+380501234513'},
    {'first_name': 'Наталія', 'last_name': 'Гаврилюк', 'phone': '+380501234514'},
    {'first_name': 'Віктор', 'last_name': 'Левченко', 'phone': '+380501234515'},
    {'first_name': 'Людмила', 'last_name': 'Онищенко', 'phone': '+380501234516'},
    {'first_name': 'Роман', 'last_name': 'Пономаренко', 'phone': '+380501234517'},
    {'first_name': 'Тетяна', 'last_name': 'Гриценко', 'phone': '+380501234518'},
    {'first_name': 'Олексій', 'last_name': 'Литвин', 'phone': '+380501234519'},
    {'first_name': 'Ірина', 'last_name': 'Жук', 'phone': '+380501234520'},
    {'first_name': 'Євген', 'last_name': 'Кузьменко', 'phone': '+380501234521'},
    {'first_name': 'Світлана', 'last_name': 'Руденко', 'phone': '+380501234522'},
    {'first_name': 'Владислав', 'last_name': 'Тищенко', 'phone': '+380501234523'},
    {'first_name': 'Олена', 'last_name': 'Марченко', 'phone': '+380501234524'},
    {'first_name': 'Артур', 'last_name': 'Бондар', 'phone': '+380501234525'},
    {'first_name': 'Валентина', 'last_name': 'Семенюк', 'phone': '+380501234526'},
    {'first_name': 'Максим', 'last_name': 'Панасюк', 'phone': '+380501234527'},
    {'first_name': 'Лариса', 'last_name': 'Остапенко', 'phone': '+380501234528'},
    {'first_name': 'Богдан', 'last_name': 'Шинкаренко', 'phone': '+380501234529'},
    {'first_name': 'Зоя', 'last_name': 'Король', 'phone': '+380501234530'},
]

VEHICLES_DATA: list[dict[str, Any]] = [
    {'vin': 'VF1DA00001234567', 'brand': 'Renault', 'model': 'Megane', 'year': 2019, 'engine': 'diesel'},
    {'vin': 'WAUZZZ8T0AA123456', 'brand': 'Audi', 'model': 'A4', 'year': 2018, 'engine': 'diesel'},
    {'vin': 'WBA3A5C5XDF123456', 'brand': 'BMW', 'model': '3 Series', 'year': 2020, 'engine': 'petrol'},
    {'vin': 'YV1DZ96C95D123456', 'brand': 'Volvo', 'model': 'XC60', 'year': 2021, 'engine': 'diesel'},
    {'vin': 'JTDKB20U083456789', 'brand': 'Toyota', 'model': 'Corolla', 'year': 2017, 'engine': 'hybrid'},
    {'vin': 'KNAGM4A78E5123456', 'brand': 'Kia', 'model': 'Sportage', 'year': 2022, 'engine': 'petrol'},
    {'vin': 'SJNFAAJ11U1234567', 'brand': 'Nissan', 'model': 'Qashqai', 'year': 2020, 'engine': 'diesel'},
    {'vin': 'TMBJA7NE5J0123456', 'brand': 'Skoda', 'model': 'Octavia', 'year': 2019, 'engine': 'petrol'},
    {'vin': 'WVWZZZ5NZLM123456', 'brand': 'Volkswagen', 'model': 'Passat', 'year': 2018, 'engine': 'diesel'},
    {'vin': 'ZAR93700001234567', 'brand': 'Fiat', 'model': 'Doblo', 'year': 2016, 'engine': 'diesel'},
    {'vin': 'XTA210930Y1234567', 'brand': 'Lada', 'model': '2109', 'year': 2008, 'engine': 'petrol'},
    {'vin': 'KMHCG41MBEU123456', 'brand': 'Hyundai', 'model': 'Tucson', 'year': 2021, 'engine': 'diesel'},
    {'vin': 'W0L0AN69XG1234567', 'brand': 'Opel', 'model': 'Astra', 'year': 2017, 'engine': 'petrol'},
    {'vin': 'VF3LJAHW8HY123456', 'brand': 'Peugeot', 'model': '3008', 'year': 2022, 'engine': 'diesel'},
    {'vin': 'SALLSSAHXGA123456', 'brand': 'Land Rover', 'model': 'Evoque', 'year': 2020, 'engine': 'diesel'},
    {'vin': 'MNAAXXMAWAK123456', 'brand': 'Ford', 'model': 'Focus', 'year': 2019, 'engine': 'petrol'},
    {'vin': 'JSAFZC32S00123456', 'brand': 'Suzuki', 'model': 'Vitara', 'year': 2021, 'engine': 'petrol'},
    {'vin': 'JM0BM543810123456', 'brand': 'Mazda', 'model': 'CX-5', 'year': 2022, 'engine': 'diesel'},
    {'vin': 'WDCDA5DB7KA123456', 'brand': 'Mercedes-Benz', 'model': 'GLC', 'year': 2020, 'engine': 'diesel'},
    {'vin': 'X7LPS8AB0JA123456', 'brand': 'Citroen', 'model': 'C4', 'year': 2018, 'engine': 'petrol'},
    {'vin': '3VWLL7AJ2BM123456', 'brand': 'Volkswagen', 'model': 'Golf', 'year': 2015, 'engine': 'petrol'},
    {'vin': 'KMHJN81VP9U123456', 'brand': 'Hyundai', 'model': 'Elantra', 'year': 2016, 'engine': 'petrol'},
    {'vin': 'YS2ED4E205B123456', 'brand': 'Scania', 'model': 'R420', 'year': 2014, 'engine': 'diesel'},
    {'vin': 'VSSZZZ5NZLR123456', 'brand': 'Seat', 'model': 'Leon', 'year': 2020, 'engine': 'petrol'},
    {'vin': 'WDD2040001A123456', 'brand': 'Mercedes-Benz', 'model': 'C-Class', 'year': 2017, 'engine': 'diesel'},
    {'vin': 'JN1TCAT11U0123456', 'brand': 'Infiniti', 'model': 'FX37', 'year': 2019, 'engine': 'petrol'},
    {'vin': 'SMTJEC2C80J123456', 'brand': 'Smart', 'model': 'Fortwo', 'year': 2018, 'engine': 'petrol'},
    {'vin': 'WBA1F120X0V123456', 'brand': 'BMW', 'model': 'X5', 'year': 2021, 'engine': 'diesel'},
    {'vin': 'VF1RFB006E1234567', 'brand': 'Renault', 'model': 'Trafic', 'year': 2019, 'engine': 'diesel'},
    {'vin': 'ZFA1990000P123456', 'brand': 'Fiat', 'model': 'Panda', 'year': 2017, 'engine': 'petrol'},
]

SUPPLIERS_DATA: list[dict[str, Any]] = [
    {'name': 'ТОВ "Автозапчастина-Сервіс"', 'contact_person': 'Олег Савчук', 'phone': '+380441234001', 'email': 'info@azs.ua'},
    {'name': 'ПП "Мотор-Деталь"', 'contact_person': 'Ігор Коваль', 'phone': '+380441234002', 'email': 'sales@motor-detail.ua'},
    {'name': 'ТОВ "Олива-Трейд"', 'contact_person': 'Андрій Лисак', 'phone': '+380441234003', 'email': 'info@olyva.ua'},
    {'name': 'ФОП "Шевченко О.В."', 'contact_person': 'Олексій Шевченко', 'phone': '+380441234004', 'email': 'oleksiy@shev.com'},
    {'name': 'ТОВ "Кузовні Системи"', 'contact_person': 'Дмитро Палій', 'phone': '+380441234005', 'email': 'info@kuzov.ua'},
]

PARTS_DATA: list[dict[str, Any]] = [
    {'name': 'Олива моторна 5W40 (4л)', 'part_number': 'OIL-5W40-4L', 'unit': 'pc', 'selling_price': 1200, 'purchase_price': 850, 'manufacturer': 'Motul'},
    {'name': 'Олива моторна 5W30 (4л)', 'part_number': 'OIL-5W30-4L', 'unit': 'pc', 'selling_price': 1100, 'purchase_price': 780, 'manufacturer': 'Mobil'},
    {'name': 'Фільтр оливний', 'part_number': 'FLT-OIL-001', 'unit': 'pc', 'selling_price': 250, 'purchase_price': 140, 'manufacturer': 'Mann-Filter'},
    {'name': 'Фільтр повітряний', 'part_number': 'FLT-AIR-001', 'unit': 'pc', 'selling_price': 350, 'purchase_price': 190, 'manufacturer': 'Mann-Filter'},
    {'name': 'Фільтр салонний', 'part_number': 'FLT-CAB-001', 'unit': 'pc', 'selling_price': 280, 'purchase_price': 160, 'manufacturer': 'Mann-Filter'},
    {'name': 'Фільтр паливний', 'part_number': 'FLT-FUL-001', 'unit': 'pc', 'selling_price': 320, 'purchase_price': 180, 'manufacturer': 'Mann-Filter'},
    {'name': 'Свічка запалювання (комплект 4шт)', 'part_number': 'SPK-SET-4', 'unit': 'set', 'selling_price': 680, 'purchase_price': 420, 'manufacturer': 'NGK'},
    {'name': 'Гальмівні колодки перед', 'part_number': 'BRK-PAD-F', 'unit': 'set', 'selling_price': 950, 'purchase_price': 580, 'manufacturer': 'Bosch'},
    {'name': 'Гальмівні колодки зад', 'part_number': 'BRK-PAD-R', 'unit': 'set', 'selling_price': 850, 'purchase_price': 520, 'manufacturer': 'Bosch'},
    {'name': 'Гальмівний диск перед', 'part_number': 'BRK-DSC-F', 'unit': 'pc', 'selling_price': 780, 'purchase_price': 450, 'manufacturer': 'TRW'},
    {'name': 'Амортизатор передній', 'part_number': 'SHP-FRONT', 'unit': 'pc', 'selling_price': 1450, 'purchase_price': 920, 'manufacturer': 'Monroe'},
    {'name': 'Кульова опора', 'part_number': 'SUS-BALL', 'unit': 'pc', 'selling_price': 420, 'purchase_price': 230, 'manufacturer': 'LemfOrder'},
    {'name': 'Сайлентблок важеля', 'part_number': 'SUS-SLNT', 'unit': 'pc', 'selling_price': 320, 'purchase_price': 180, 'manufacturer': 'LemfOrder'},
    {'name': 'Стійка стабілізатора', 'part_number': 'SUS-STAB', 'unit': 'pc', 'selling_price': 280, 'purchase_price': 150, 'manufacturer': 'LemfOrder'},
    {'name': 'Акумулятор 60Ah', 'part_number': 'BAT-60AH', 'unit': 'pc', 'selling_price': 2800, 'purchase_price': 1950, 'manufacturer': 'Varta'},
    {'name': 'Антифриз (5л)', 'part_number': 'ANT-5L', 'unit': 'pc', 'selling_price': 650, 'purchase_price': 420, 'manufacturer': 'Castrol'},
    {'name': 'Ремінь ГРМ (комплект)', 'part_number': 'BLT-TMG-SET', 'unit': 'set', 'selling_price': 1800, 'purchase_price': 1200, 'manufacturer': 'Contitech'},
    {'name': 'Ролик ременя ГРМ', 'part_number': 'BLT-TMG-RLR', 'unit': 'pc', 'selling_price': 520, 'purchase_price': 310, 'manufacturer': 'INA'},
    {'name': 'Помпа системи охолодження', 'part_number': 'CWL-PMP', 'unit': 'pc', 'selling_price': 1100, 'purchase_price': 720, 'manufacturer': 'Grundfos'},
    {'name': 'Термостат', 'part_number': 'CWL-THRM', 'unit': 'pc', 'selling_price': 380, 'purchase_price': 210, 'manufacturer': 'Vernet'},
    {'name': 'Лампа головного світла H7', 'part_number': 'LMP-H7', 'unit': 'pc', 'selling_price': 180, 'purchase_price': 90, 'manufacturer': 'Osram'},
    {'name': 'Щітки склоочисника (комплект)', 'part_number': 'WIP-SET', 'unit': 'set', 'selling_price': 350, 'purchase_price': 190, 'manufacturer': 'Bosch'},
    {'name': 'Рідина гальмівна (1л)', 'part_number': 'BRK-FLUID', 'unit': 'pc', 'selling_price': 250, 'purchase_price': 140, 'manufacturer': 'Castrol'},
    {'name': 'Прокладка клапанної кришки', 'part_number': 'GSK-VLV', 'unit': 'pc', 'selling_price': 280, 'purchase_price': 150, 'manufacturer': 'Victor Reinz'},
    {'name': 'Датчик кисню (лямбда)', 'part_number': 'SNS-O2', 'unit': 'pc', 'selling_price': 1250, 'purchase_price': 800, 'manufacturer': 'Bosch'},
    {'name': 'Рідина склоомивача (5л)', 'part_number': 'WSH-5L', 'unit': 'pc', 'selling_price': 180, 'purchase_price': 90, 'manufacturer': 'Sonax'},
]

WORK_ORDER_CONFIGS: list[dict[str, Any]] = [
    {
        'statuses': ['completed', 'completed', 'completed', 'completed', 'completed',
                     'completed', 'in_progress', 'completed', 'completed', 'completed',
                     'completed', 'completed', 'completed', 'completed', 'completed',
                     'completed', 'completed', 'in_progress', 'completed', 'awaiting_payment',
                     'completed', 'completed', 'completed', 'completed', 'draft',
                     'completed', 'completed', 'completed', 'completed', 'completed'],
        'services_count': (1, 3),
        'parts_count': (0, 2),
    },
]

# Вартість нормо-години за категоріями робіт
CATEGORY_HOURLY_RATES: dict[str, Decimal] = {
    'maintenance': Decimal('500'),
    'diagnostics': Decimal('600'),
    'repair': Decimal('700'),
    'electrical': Decimal('650'),
    'bodywork': Decimal('750'),
    'tyre': Decimal('400'),
    'detailing': Decimal('500'),
    'other': Decimal('550'),
}


# ======================================================================
# КОМАНДА
# ======================================================================

class Command(BaseCommand):
    """Створює імітацію роботи автосервісу за 3 місяці."""

    help = 'Створює імітацію роботи автосервісу за 3 місяці'

    def add_arguments(self, parser: CommandParser) -> None:
        """Додає аргументи команди."""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Очистити існуючі дані перед створенням',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Виконує імітацію."""
        force: bool = options.get('force', False)

        if force:
            self._clean_data()
            self.stdout.write(self.style.WARNING('Стары дані видалено.'))

        company = Company.objects.filter(name='Автосервіс Столиця').first()
        if not company:
            self.stderr.write('Компанія "Автосервіс Столиця" не знайдена. Спочатку виконайте створення компанії.')
            return

        # Перевірка, чи вже є дані
        if Employee.objects.filter(company=company).exists() and not force:
            self.stdout.write(self.style.WARNING(
                'Дані для "Автосервіс Столиця" вже існують. Використайте --force для перестворення.'
            ))
            return

        self.stdout.write('>>  Створюю імітацію роботи автосервісу за 3 місяці...\n')

        with transaction.atomic():
            employees = self._create_employees(company)
            self.stdout.write(f'  OK  Співробітники: {len(employees)} осіб')

            clients = self._create_clients(company)
            self.stdout.write(f'  OK  Клієнти: {len(clients)} осіб')

            vehicles = self._create_vehicles(company, clients)
            self.stdout.write(f'  OK  Автомобілі: {len(vehicles)} од.')

            suppliers = self._create_suppliers(company)
            self.stdout.write(f'  OK  Постачальники: {len(suppliers)} од.')

            parts = self._create_parts(company)
            self.stdout.write(f'  OK  Запчастини: {len(parts)} найм.')

            purchasers = Employee.objects.filter(
                company=company,
                roles__codename='purchaser',
            )

            # Створюємо закупівлі (4 за 3 місяці)
            purchase_count = self._create_purchase_orders(
                company, suppliers, parts, employees, purchasers.first(),
            )
            self.stdout.write(f'  OK  Закупівлі: {purchase_count} од.')

            # Створюємо заказ-наряди
            mechanics = list(Employee.objects.filter(
                company=company,
                roles__codename='mechanic',
            ))
            managers = list(Employee.objects.filter(
                company=company,
                roles__codename='manager',
            ))
            admin_emp = Employee.objects.filter(
                company=company,
                roles__codename='admin',
            ).first()

            today = tz.now().date()
            start_date = today - timedelta(days=90)

            work_orders_count = self._create_work_orders(
                company, clients, vehicles, mechanics, managers, admin_emp,
                start_date, today,
            )
            self.stdout.write(f'  OK  Заказ-наряди: {work_orders_count} од.')

        # Підрахунок результатів
        self._print_summary(company)

    # ------------------------------------------------------------------
    # ОЧИЩЕННЯ
    # ------------------------------------------------------------------

    def _clean_data(self) -> None:
        """Очищує всі дані імітації, крім Company, Role та WorkType."""
        from django.db import connection
        tables = [
            'workorders_workorderpart',
            'workorders_workorderservice',
            'workorders_workorder',
            'parts_partlot',
            'purchases_supplierpayment',
            'purchases_purchaseorderitem',
            'purchases_purchaseorder',
            'vehicles_vehicle',
            'clients_client',
            'suppliers_supplier',
            'parts_part',
            'accounts_employee',
        ]
        for table in tables:
            with connection.cursor() as cursor:
                try:
                    cursor.execute(f'DELETE FROM "{table}"')
                except Exception:
                    pass  # таблиці може не бути

        # Видалити створених користувачів (крім суперюзера)
        User.objects.filter(
            employee__isnull=False,
        ).delete()

    # ------------------------------------------------------------------
    # СТВОРЕННЯ СПІВРОБІТНИКІВ
    # ------------------------------------------------------------------

    def _create_employees(self, company: Company) -> list[Employee]:
        """Створює співробітників."""
        employees: list[Employee] = []
        for emp_data in EMPLOYEES_DATA:
            user, _ = User.objects.get_or_create(
                username=emp_data['username'],
                defaults={
                    'first_name': emp_data['first_name'],
                    'last_name': emp_data['last_name'],
                    'email': f"{emp_data['username']}@autoservice.ua",
                    'is_staff': emp_data['username'] in ('admin', 'director'),
                },
            )
            if not user.check_password('12345'):
                user.set_password('12345')
                user.save()

            employee, created = Employee.objects.get_or_create(
                user=user,
                company=company,
                defaults={
                    'phone': emp_data['phone'],
                    'parts_sale_percent': emp_data['parts_sale_percent'],
                    'labor_percent': emp_data['labor_percent'],
                    'is_active': True,
                },
            )
            if created:
                roles = Role.objects.filter(codename__in=emp_data['roles'])
                employee.roles.set(roles)
            employees.append(employee)

        return employees

    # ------------------------------------------------------------------
    # СТВОРЕННЯ КЛІЄНТІВ
    # ------------------------------------------------------------------

    def _create_clients(self, company: Company) -> list[Client]:
        """Створює клієнтів."""
        clients: list[Client] = []
        for data in CLIENTS_DATA:
            client, _ = Client.objects.get_or_create(
                phone=data['phone'],
                company=company,
                defaults={
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                },
            )
            clients.append(client)
        return clients

    # ------------------------------------------------------------------
    # СТВОРЕННЯ АВТОМОБІЛІВ
    # ------------------------------------------------------------------

    def _create_vehicles(
        self,
        company: Company,
        clients: list[Client],
    ) -> list[Vehicle]:
        """Створює автомобілі."""
        vehicles: list[Vehicle] = []
        for i, data in enumerate(VEHICLES_DATA):
            client = clients[i % len(clients)]
            vehicle, _ = Vehicle.objects.get_or_create(
                vin_code=data['vin'],
                company=company,
                defaults={
                    'brand': data['brand'],
                    'model': data['model'],
                    'year': data['year'],
                    'engine_type': data['engine'],
                    'client': client,
                },
            )
            vehicles.append(vehicle)
        return vehicles

    # ------------------------------------------------------------------
    # СТВОРЕННЯ ПОСТАЧАЛЬНИКІВ
    # ------------------------------------------------------------------

    def _create_suppliers(self, company: Company) -> list[Supplier]:
        """Створює постачальників."""
        suppliers: list[Supplier] = []
        for data in SUPPLIERS_DATA:
            supplier, _ = Supplier.objects.get_or_create(
                name=data['name'],
                company=company,
                defaults={
                    'contact_person': data['contact_person'],
                    'phone': data['phone'],
                    'email': data['email'],
                    'is_active': True,
                },
            )
            suppliers.append(supplier)
        return suppliers

    # ------------------------------------------------------------------
    # СТВОРЕННЯ ЗАПЧАСТИН
    # ------------------------------------------------------------------

    def _create_parts(self, company: Company) -> list[Part]:
        """Створює запчастини."""
        parts: list[Part] = []
        for data in PARTS_DATA:
            part, _ = Part.objects.get_or_create(
                part_number=data['part_number'],
                company=company,
                defaults={
                    'name': data['name'],
                    'unit': data['unit'],
                    'selling_price': data['selling_price'],
                    'manufacturer': data.get('manufacturer', ''),
                    'quantity_on_hand': Decimal('0'),
                    'is_active': True,
                },
            )
            parts.append(part)
        return parts

    # ------------------------------------------------------------------
    # СТВОРЕННЯ ЗАКУПІВЕЛЬ
    # ------------------------------------------------------------------

    def _create_purchase_orders(
        self,
        company: Company,
        suppliers: list[Supplier],
        parts: list[Part],
        employees: list[Employee],
        purchaser: Employee | None,
    ) -> int:
        """Створює закупівлі та оприбутковує товар."""
        from purchases.services import PurchaseOrderService

        today = tz.now().date()
        start_date = today - timedelta(days=90)
        count = 0

        # 4 закупівлі: на початку 1-го, 2-го, 3-го місяця + додаткова
        purchase_dates = [
            start_date + timedelta(days=3),
            start_date + timedelta(days=30),
            start_date + timedelta(days=55),
            start_date + timedelta(days=78),
        ]

        for idx, po_date in enumerate(purchase_dates):
            supplier = suppliers[idx % len(suppliers)]

            # Визначаємо позиції для закупівлі
            item_configs = self._get_purchase_items(parts, idx)

            order_number = f"SIM-{po_date.strftime('%Y%m%d')}-{idx + 1}"

            try:
                with transaction.atomic():
                    po = PurchaseOrder.objects.create(
                        order_number=order_number,
                        supplier=supplier,
                        status='ordered',
                        company=company,
                        created_by=purchaser or employees[0],
                    )

                    receive_data: list[tuple[PurchaseOrderItem, Decimal]] = []

                    for part, qty, price in item_configs:
                        item = PurchaseOrderItem.objects.create(
                            purchase_order=po,
                            part=part,
                            quantity_ordered=qty,
                            quantity_received=Decimal('0'),
                            unit_price=price,
                        )
                        receive_data.append((item, qty))

                    # Оприбутковуємо
                    PurchaseOrderService.receive_items(po, receive_data)

                    # Створюємо платіж
                    total_amount = sum(qty * price for _, qty, price in item_configs)
                    payment_number = f"PAY-SIM-{po_date.strftime('%Y%m%d')}-{idx + 1}"
                    SupplierPayment.objects.create(
                        payment_number=payment_number,
                        status='completed',
                        supplier=supplier,
                        company=company,
                        amount=total_amount,
                        payment_date=po_date + timedelta(days=random_int(1, 5)),
                        payment_type='bank_transfer',
                        purchase_order=po,
                        created_by=purchaser or employees[0],
                    )

                    count += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f'  !!  Помилка створення закупівлі {order_number}: {e}'
                ))

        return count

    def _get_purchase_items(
        self,
        parts: list[Part],
        order_idx: int,
    ) -> list[tuple[Part, Decimal, Decimal]]:
        """Визначає склад закупівлі."""
        items: list[tuple[Part, Decimal, Decimal]] = []

        # Базові позиції (олива, фільтри)
        base_indices = [0, 1, 2, 3, 4, 15, 16, 22, 25]
        for idx in base_indices:
            if idx < len(parts):
                part = parts[idx]
                qty = Decimal(str(random_int(3, 10)))
                price = PARTS_DATA[idx]['purchase_price']
                items.append((part, qty, Decimal(str(price))))

        # Додаткові позиції залежно від місяця
        extra_pool = {
            0: [5, 6, 7, 8, 23],    # місяць 1: свічки, колодки
            1: [9, 10, 11, 12, 13],  # місяць 2: амортизатори, кульові
            2: [14, 17, 18, 19, 20], # місяць 3: акумулятор, ролики
            3: [5, 6, 20, 21, 24],   # додатково
        }
        extra_indices = extra_pool.get(order_idx, [])
        for idx in extra_indices:
            if idx < len(parts):
                part = parts[idx]
                qty = Decimal(str(random_int(2, 5)))
                price = PARTS_DATA[idx]['purchase_price']
                items.append((part, qty, Decimal(str(price))))

        return items

    # ------------------------------------------------------------------
    # СТВОРЕННЯ ЗАКАЗ-НАРЯДІВ
    # ------------------------------------------------------------------

    def _create_work_orders(
        self,
        company: Company,
        clients: list[Client],
        vehicles: list[Vehicle],
        mechanics: list[Employee],
        managers: list[Employee],
        admin_emp: Employee | None,
        start_date: date,
        end_date: date,
    ) -> int:
        """Створює заказ-наряди, розподілені за 3 місяці."""
        work_types = list(WorkType.objects.filter(
            company=company, is_active=True,
        ))
        parts = list(Part.objects.filter(company=company, is_active=True))

        total_days = (end_date - start_date).days
        count = 0

        # Генеруємо 55 нарядів з випадковими датами
        import random
        random.seed(42)

        for order_num in range(55):
            # Випадковий день в межах 3 місяців
            day_offset = random.randint(0, total_days)
            order_date = start_date + timedelta(days=day_offset)

            # Забезпечуємо робочий день (понеділок-п'ятниця)
            while order_date.weekday() >= 5:
                day_offset = (day_offset + 1) % (total_days + 1)
                order_date = start_date + timedelta(days=day_offset)

            order_datetime = tz.make_aware(
                datetime(
                    order_date.year, order_date.month, order_date.day,
                    random.randint(9, 17), random.randint(0, 59),
                ),
            )

            # Вибираємо випадкові клієнта та авто
            client = random.choice(clients)
            client_vehicles = [v for v in vehicles if v.client_id == client.pk]
            if not client_vehicles:
                continue
            vehicle = random.choice(client_vehicles)

            # Статус (ранні наряди частіше завершені)
            if order_date < end_date - timedelta(days=5):
                status_weights = ['completed'] * 15 + ['in_progress'] * 2 + ['awaiting_payment'] * 2 + ['cancelled'] * 1
            else:
                status_weights = ['completed'] * 5 + ['in_progress'] * 3 + ['draft'] * 1 + ['awaiting_payment'] * 1

            status = random.choice(status_weights)

            # Хто створив
            creator = random.choice(managers) if managers else (admin_emp or mechanics[0])

            # Пробіг
            mileage = random.randint(50000, 250000)

            try:
                with transaction.atomic():
                    work_order = WorkOrder.objects.create(
                        company=company,
                        vehicle=vehicle,
                        client=client,
                        created_by=creator,
                        status=status,
                        mileage=mileage,
                        notes=self._generate_notes(status),
                    )

                    # Коригуємо created_at
                    WorkOrder.objects.filter(pk=work_order.pk).update(
                        created_at=order_datetime,
                        updated_at=order_datetime,
                    )
                    work_order.refresh_from_db()

                    # Додаємо послуги (1-3)
                    num_services = random.randint(1, 3)
                    used_work_types: list[int] = []
                    for _ in range(num_services):
                        wt = random.choice(work_types)
                        if wt.pk in used_work_types and len(used_work_types) < len(work_types):
                            continue
                        used_work_types.append(wt.pk)

                        quantity = Decimal(str(random.randint(1, 4)))
                        category = wt.category
                        hourly_rate = CATEGORY_HOURLY_RATES.get(category, Decimal('500'))
                        unit_price = hourly_rate * quantity

                        # Виконавець-механік (тільки для завершених/в роботі)
                        mechanic = random.choice(mechanics) if status not in ('draft', 'cancelled') else None

                        # Випадковий опис
                        desc_parts = [
                            wt.description[:50] if wt.description else '',
                            f"за {quantity} нормо-год",
                        ]
                        desc = ', '.join(filter(None, desc_parts))

                        WorkOrderService.objects.create(
                            work_order=work_order,
                            work_type=wt,
                            quantity=quantity,
                            unit_price=unit_price,
                            employee=mechanic,
                            description=desc,
                        )

                    # Додаємо запчастини (0-2)
                    num_parts = random.randint(0, 2)
                    for _ in range(num_parts):
                        part = random.choice(parts)

                        # Перевіряємо наявність на складі
                        qty_needed = Decimal(str(random.randint(1, 3)))
                        if part.quantity_on_hand < qty_needed:
                            # Спробуємо іншу деталь
                            available_parts = [p for p in parts if p.quantity_on_hand >= qty_needed]
                            if not available_parts:
                                continue
                            part = random.choice(available_parts)

                        # Знаходимо партію
                        lot = PartLot.objects.filter(
                            part=part,
                            company=company,
                        ).filter(
                            quantity__gt=F('quantity_used'),
                        ).order_by('created_at').first()

                        if not lot:
                            continue

                        # Споживаємо зі складу
                        try:
                            PartService.decrease_stock(part, qty_needed)
                        except ValueError:
                            continue

                        # Оновлюємо PartLot
                        PartLot.objects.filter(pk=lot.pk).update(
                            quantity_used=F('quantity_used') + qty_needed,
                        )
                        lot.refresh_from_db()

                        WorkOrderPart.objects.create(
                            work_order=work_order,
                            part=part,
                            quantity=qty_needed,
                            unit_price=part.selling_price,
                            part_lot=lot,
                            purchase_price=lot.purchase_price,
                        )

                    count += 1

            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f'  !!  Помилка наряду #{order_num + 1}: {e}'
                ))
                continue

        return count

    def _generate_notes(self, status: str) -> str:
        """Генерує випадкову нотатку."""
        import random
        notes_pool: list[str] = [
            '', '', '', '',
            'Клієнт скаржиться на сторонній шум при повороті.',
            'Рекомендовано заміну масла через 5000 км.',
            'Двигун працює нестабільно на холодну.',
            'Періодично горить Check Engine.',
            'Автомобіль привезли евакуатором.',
            'Клієнт просить перевірити підвіску.',
            'Планове ТО за регламентом.',
        ]
        if status == 'cancelled':
            return 'Клієнт відмовився від ремонту.'
        return random.choice(notes_pool)

    # ------------------------------------------------------------------
    # ПІДСУМКИ
    # ------------------------------------------------------------------

    def _print_summary(self, company: Company) -> None:
        """Виводить зведення."""
        from django.db.models import Count, Sum

        emp_count = Employee.objects.filter(company=company).count()
        client_count = Client.objects.filter(company=company).count()
        vehicle_count = Vehicle.objects.filter(company=company).count()
        supplier_count = Supplier.objects.filter(company=company).count()
        part_count = Part.objects.filter(company=company).count()

        wo_count = WorkOrder.objects.filter(company=company).count()
        wo_completed = WorkOrder.objects.filter(company=company, status='completed').count()
        wo_in_progress = WorkOrder.objects.filter(company=company, status='in_progress').count()

        po_count = PurchaseOrder.objects.filter(company=company).count()
        payment_count = SupplierPayment.objects.filter(company=company).count()

        total_services = WorkOrderService.objects.filter(
            work_order__company=company,
        ).aggregate(
            total=Sum(F('quantity') * F('unit_price')),
        )['total'] or Decimal('0')

        total_parts = WorkOrderPart.objects.filter(
            work_order__company=company,
        ).aggregate(
            total=Sum(F('quantity') * F('unit_price')),
        )['total'] or Decimal('0')

        total_revenue = total_services + total_parts

        self.stdout.write('\n' + '=' * 55)
        self.stdout.write(self.style.SUCCESS(
            f'  ** ІМІТАЦІЮ ЗАВЕРШЕНО — "{company.name}"'
        ))
        self.stdout.write('=' * 55)
        self.stdout.write(f'  Період: 3 місяці')
        self.stdout.write(f'  Співробітники:   {emp_count}')
        self.stdout.write(f'  Клієнти:          {client_count}')
        self.stdout.write(f'  Автомобілі:       {vehicle_count}')
        self.stdout.write(f'  Постачальники:    {supplier_count}')
        self.stdout.write(f'  Запчастини:       {part_count}')
        self.stdout.write(f'  Закупівлі:        {po_count}')
        self.stdout.write(f'  Платежі:          {payment_count}')
        self.stdout.write(f'  Заказ-наряди:     {wo_count}')
        self.stdout.write(f'      + Завершено:    {wo_completed}')
        self.stdout.write(f'      + В роботі:     {wo_in_progress}')
        self.stdout.write(f'      + Інші:         {wo_count - wo_completed - wo_in_progress}')
        self.stdout.write(f'  -----------------------------')
        self.stdout.write(f'  Виторг за роботи: {total_services:>10,.2f} грн')
        self.stdout.write(f'  Виторг за запчастини: {total_parts:>7,.2f} грн')
        self.stdout.write(f'  Загальний виторг: {total_revenue:>10,.2f} грн')
        self.stdout.write('=' * 55)
        self.stdout.write(
            '  Паролі всіх співробітників: 12345\n'
        )


# ======================================================================
# ДОПОМІЖНІ ФУНКЦІЇ
# ======================================================================

def random_int(min_val: int, max_val: int) -> int:
    """Повертає випадкове ціле число."""
    import random
    return random.randint(min_val, max_val)
