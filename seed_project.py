"""Симуляція 2 місяців роботи автосервісу: закупівлі, запчастини, наряди."""
from __future__ import annotations

import datetime
from datetime import date, timedelta
from decimal import Decimal
from random import randint, seed as random_seed
from typing import Any

import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import F
from django.utils import timezone

from accounts.models import Employee
from company.models import Company
from parts.models import Part, PartLot
from parts.services import PartService
from purchases.models import PurchaseOrder, PurchaseOrderItem
from purchases.services import PurchaseOrderService
from suppliers.models import Supplier
from vehicles.models import Vehicle
from workorders.models import WorkOrder, WorkOrderPart, WorkOrderService
from worktypes.models import WorkType

# =====================================================================
# НАЛАШТУВАННЯ
# =====================================================================
COMPANY_ID = 1
random_seed(42)


# =====================================================================
# ДОПОМІЖНІ ФУНКЦІЇ
# =====================================================================
def random_date(start: date, end: date) -> date:
    """Випадкова дата в діапазоні."""
    delta = (end - start).days
    return start + timedelta(days=randint(0, delta))


def make_aware(d: date) -> datetime.datetime:
    """Перетворює date на datetime з таймзоною."""
    return timezone.make_aware(
        datetime.datetime.combine(d, datetime.datetime.min.time())
    )


# =====================================================================
# 1. ПОСТАЧАЛЬНИКИ
# =====================================================================
def create_suppliers() -> list[Supplier]:
    print('\n=== 1. Створення постачальників ===')
    company = Company.objects.get(pk=COMPANY_ID)
    data = [
        {'name': 'ТОВ "АвтоЗапчастина"',      'contact_person': 'Сергій Петренко',  'phone': '+380501112233', 'email': 'info@autozap.ua'},
        {'name': 'ПП "Олімп-Авто"',             'contact_person': 'Олексій Іваненко', 'phone': '+380501112234', 'email': 'olimp@auto.ua'},
        {'name': 'ТОВ "Мотор-Деталь"',          'contact_person': 'Ігор Коваленко',   'phone': '+380501112235', 'email': 'motor@detail.ua'},
        {'name': 'ФОП "Шевченко О.І."',        'contact_person': 'Олександр Шевченко','phone': '+380501112236', 'email': 'shevchenko@ukr.net'},
        {'name': 'ТОВ "Євро-Авто"',            'contact_person': 'Андрій Бойко',     'phone': '+380501112237', 'email': 'euroauto@euro.ua'},
    ]
    created = []
    for d in data:
        sup, _ = Supplier.objects.get_or_create(name=d['name'], company=company, defaults=d)
        created.append(sup)
        print(f'  [OK] {sup.name}')
    return created


# =====================================================================
# 2. АВТОМОБІЛІ
# =====================================================================
def create_vehicles() -> list[Vehicle]:
    print('\n=== 2. Створення автомобілів ===')
    company = Company.objects.get(pk=COMPANY_ID)
    data = [
        {'vin_code': 'WVWZZZ1JZXW000001', 'brand': 'Volkswagen', 'model': 'Passat B7',     'year': 2014, 'engine_type': Vehicle.EngineType.DIESEL,  'engine_displacement': Decimal('2.0')},
        {'vin_code': 'SJNFBAJ11U1234567', 'brand': 'Nissan',     'model': 'Qashqai J11',   'year': 2019, 'engine_type': Vehicle.EngineType.PETROL,  'engine_displacement': Decimal('1.6')},
        {'vin_code': 'XTA210930Y1234567', 'brand': 'Lada',       'model': '2109',           'year': 2006, 'engine_type': Vehicle.EngineType.PETROL,  'engine_displacement': Decimal('1.5')},
        {'vin_code': 'VF1RFB00454123456', 'brand': 'Renault',    'model': 'Megane III',     'year': 2012, 'engine_type': Vehicle.EngineType.DIESEL,  'engine_displacement': Decimal('1.5')},
        {'vin_code': 'KMHDU41BPBU123456', 'brand': 'Hyundai',    'model': 'Tucson ix35',    'year': 2015, 'engine_type': Vehicle.EngineType.DIESEL,  'engine_displacement': Decimal('2.0')},
        {'vin_code': 'WAUZZZ8V9PA123456', 'brand': 'Audi',       'model': 'A4 B9',          'year': 2017, 'engine_type': Vehicle.EngineType.PETROL,  'engine_displacement': Decimal('2.0')},
        {'vin_code': 'WBA3A51080F123456', 'brand': 'BMW',        'model': '320d E90',       'year': 2008, 'engine_type': Vehicle.EngineType.DIESEL,  'engine_displacement': Decimal('2.0')},
        {'vin_code': 'Z94CB41AABR123456', 'brand': 'Daewoo',     'model': 'Lanos',          'year': 2007, 'engine_type': Vehicle.EngineType.PETROL,  'engine_displacement': Decimal('1.5')},
    ]
    created = []
    for d in data:
        veh, _ = Vehicle.objects.get_or_create(vin_code=d['vin_code'], company=company, defaults=d)
        created.append(veh)
        print(f'  [OK] {veh}')
    return created


# =====================================================================
# 3. ЗАПЧАСТИНИ
# =====================================================================
def create_parts() -> list[Part]:
    print('\n=== 3. Створення запчастин ===')
    company = Company.objects.get(pk=COMPANY_ID)
    data: list[dict[str, Any]] = [
        {'name': 'Олива моторна 5W-40 (4л)',      'part_number': 'OIL-5W40-4', 'manufacturer': 'Mobil',   'unit': 'pc', 'selling_price': Decimal('1200'), 'min_quantity': Decimal('3'), 'location': 'A1'},
        {'name': 'Олива моторна 5W-30 (4л)',      'part_number': 'OIL-5W30-4', 'manufacturer': 'Castrol', 'unit': 'pc', 'selling_price': Decimal('1350'), 'min_quantity': Decimal('3'), 'location': 'A2'},
        {'name': 'Олива трансмісійна 75W-90 (1л)','part_number': 'OIL-75W90-1','manufacturer': 'Motul',   'unit': 'pc', 'selling_price': Decimal('450'),  'min_quantity': Decimal('5'), 'location': 'A3'},
        {'name': 'Антифриз Concentrate (5л)',     'part_number': 'ANT-5L',     'manufacturer': 'Hepu',    'unit': 'pc', 'selling_price': Decimal('650'),  'min_quantity': Decimal('2'), 'location': 'A4'},
        {'name': 'Гальмівна рідина DOT4 (0.5л)',  'part_number': 'BRAKE-DOT4', 'manufacturer': 'Bosch',   'unit': 'pc', 'selling_price': Decimal('180'),  'min_quantity': Decimal('5'), 'location': 'A5'},
        {'name': 'Фільтр масляний',                'part_number': 'FIL-OIL-001','manufacturer': 'Mann',    'unit': 'pc', 'selling_price': Decimal('150'),  'min_quantity': Decimal('10'), 'location': 'B1'},
        {'name': 'Фільтр повітряний',              'part_number': 'FIL-AIR-001','manufacturer': 'Mann',    'unit': 'pc', 'selling_price': Decimal('200'),  'min_quantity': Decimal('5'),  'location': 'B2'},
        {'name': 'Фільтр салонний',                'part_number': 'FIL-CAB-001','manufacturer': 'Mann',    'unit': 'pc', 'selling_price': Decimal('180'),  'min_quantity': Decimal('5'),  'location': 'B3'},
        {'name': 'Фільтр паливний',                'part_number': 'FIL-FUL-001','manufacturer': 'Mann',    'unit': 'pc', 'selling_price': Decimal('250'),  'min_quantity': Decimal('3'),  'location': 'B4'},
        {'name': 'Колодки гальмівні перед',        'part_number': 'BRK-PAD-F',  'manufacturer': 'TRW',     'unit': 'set','selling_price': Decimal('650'),  'min_quantity': Decimal('3'), 'location': 'C1'},
        {'name': 'Колодки гальмівні зад',          'part_number': 'BRK-PAD-R',  'manufacturer': 'TRW',     'unit': 'set','selling_price': Decimal('600'),  'min_quantity': Decimal('3'), 'location': 'C2'},
        {'name': 'Диски гальмівні перед',          'part_number': 'BRK-DIS-F',  'manufacturer': 'Brembo',  'unit': 'set','selling_price': Decimal('1500'), 'min_quantity': Decimal('2'), 'location': 'C3'},
        {'name': 'Диски гальмівні зад',            'part_number': 'BRK-DIS-R',  'manufacturer': 'Brembo',  'unit': 'set','selling_price': Decimal('1300'), 'min_quantity': Decimal('2'), 'location': 'C4'},
        {'name': 'Амортизатор передній',           'part_number': 'SHP-FR',     'manufacturer': 'KYB',     'unit': 'pc', 'selling_price': Decimal('1200'), 'min_quantity': Decimal('2'), 'location': 'D1'},
        {'name': 'Амортизатор задній',             'part_number': 'SHP-RR',     'manufacturer': 'KYB',     'unit': 'pc', 'selling_price': Decimal('1100'), 'min_quantity': Decimal('2'), 'location': 'D2'},
        {'name': 'Кульова опора',                  'part_number': 'BALL-JNT',   'manufacturer': 'Lemforder','unit': 'pc','selling_price': Decimal('350'),  'min_quantity': Decimal('4'), 'location': 'D3'},
        {'name': 'Стійка стабілізатора',           'part_number': 'STAB-LINK',  'manufacturer': 'Febest',  'unit': 'pc', 'selling_price': Decimal('180'),  'min_quantity': Decimal('4'), 'location': 'D4'},
        {'name': 'Рульовий наконечник',            'part_number': 'TIE-ROD',    'manufacturer': 'TRW',     'unit': 'pc', 'selling_price': Decimal('280'),  'min_quantity': Decimal('4'), 'location': 'D5'},
        {'name': 'Свічка запалювання',             'part_number': 'SPARK-PL',   'manufacturer': 'NGK',     'unit': 'pc', 'selling_price': Decimal('120'),  'min_quantity': Decimal('16'), 'location': 'E1'},
        {'name': 'Акумулятор 60Ah',                'part_number': 'BAT-60',     'manufacturer': 'Varta',   'unit': 'pc', 'selling_price': Decimal('2800'), 'min_quantity': Decimal('2'), 'location': 'E2'},
        {'name': 'Акумулятор 74Ah',                'part_number': 'BAT-74',     'manufacturer': 'Bosch',   'unit': 'pc', 'selling_price': Decimal('3500'), 'min_quantity': Decimal('1'), 'location': 'E3'},
        {'name': 'Лампа H4',                       'part_number': 'LAMP-H4',    'manufacturer': 'Philips', 'unit': 'pc', 'selling_price': Decimal('150'),  'min_quantity': Decimal('10'), 'location': 'E4'},
        {'name': 'Ремінь ГРМ (комплект)',          'part_number': 'TIM-BELT',   'manufacturer': 'Contitech','unit': 'set','selling_price': Decimal('1800'), 'min_quantity': Decimal('2'), 'location': 'F1'},
        {'name': 'Ремінь генератора',              'part_number': 'ALT-BELT',   'manufacturer': 'Gates',   'unit': 'pc', 'selling_price': Decimal('250'),  'min_quantity': Decimal('3'), 'location': 'F2'},
        {'name': 'Щітки склоочисника (комплект)',  'part_number': 'WIPER-SET',  'manufacturer': 'Bosch',   'unit': 'set','selling_price': Decimal('350'),  'min_quantity': Decimal('5'), 'location': 'G1'},
    ]
    created = []
    for d in data:
        part, _ = Part.objects.get_or_create(
            part_number=d['part_number'],
            company=company,
            defaults=d,
        )
        created.append(part)
    print(f'  [OK] Створено {len(created)} запчастин')
    return created


# =====================================================================
# 4. ЗАКУПІВЛІ З ОПРИБУТКУВАННЯМ
# =====================================================================
def create_purchases(suppliers: list[Supplier], parts: list[Part], employees: list[Employee]):
    print('\n=== 4. Створення закупівель та оприбуткування ===')
    company = Company.objects.get(pk=COMPANY_ID)
    purchaser = next(e for e in employees if e.has_role('purchaser'))
    part_map: dict[str, Part] = {p.part_number: p for p in parts}

    purchases_data: list[dict[str, Any]] = [
        {
            'supplier': suppliers[0],
            'date': date(2026, 4, 2),
            'items': [
                (part_map['OIL-5W40-4'],   10, Decimal('850')),
                (part_map['OIL-5W30-4'],   10, Decimal('920')),
                (part_map['FIL-OIL-001'],  30, Decimal('90')),
                (part_map['FIL-AIR-001'],  15, Decimal('120')),
                (part_map['FIL-CAB-001'],  15, Decimal('100')),
            ],
        },
        {
            'supplier': suppliers[0],
            'date': date(2026, 5, 5),
            'items': [
                (part_map['OIL-5W40-4'],   5,  Decimal('860')),
                (part_map['OIL-5W30-4'],   5,  Decimal('930')),
                (part_map['FIL-OIL-001'],  20, Decimal('95')),
                (part_map['FIL-AIR-001'],  10, Decimal('125')),
            ],
        },
        {
            'supplier': suppliers[1],
            'date': date(2026, 4, 5),
            'items': [
                (part_map['BRK-PAD-F'],    8,  Decimal('380')),
                (part_map['BRK-PAD-R'],    8,  Decimal('350')),
                (part_map['BRK-DIS-F'],    4,  Decimal('950')),
                (part_map['BRK-DIS-R'],    4,  Decimal('850')),
                (part_map['SHP-FR'],       4,  Decimal('820')),
                (part_map['SHP-RR'],       4,  Decimal('750')),
            ],
        },
        {
            'supplier': suppliers[1],
            'date': date(2026, 5, 15),
            'items': [
                (part_map['BRK-PAD-F'],    5,  Decimal('390')),
                (part_map['BRK-PAD-R'],    5,  Decimal('360')),
                (part_map['BALL-JNT'],      8,  Decimal('210')),
                (part_map['STAB-LINK'],     8,  Decimal('100')),
            ],
        },
        {
            'supplier': suppliers[2],
            'date': date(2026, 4, 8),
            'items': [
                (part_map['TIM-BELT'],     3,  Decimal('1100')),
                (part_map['ALT-BELT'],     5,  Decimal('140')),
                (part_map['SPARK-PL'],     40, Decimal('60')),
                (part_map['LAMP-H4'],      20, Decimal('70')),
            ],
        },
        {
            'supplier': suppliers[2],
            'date': date(2026, 5, 12),
            'items': [
                (part_map['TIM-BELT'],     2,  Decimal('1120')),
                (part_map['SPARK-PL'],     20, Decimal('65')),
                (part_map['OIL-75W90-1'],  10, Decimal('280')),
            ],
        },
        {
            'supplier': suppliers[3],
            'date': date(2026, 4, 12),
            'items': [
                (part_map['ANT-5L'],       5,  Decimal('400')),
                (part_map['BRAKE-DOT4'],  10, Decimal('100')),
                (part_map['WIPER-SET'],    8,  Decimal('200')),
                (part_map['BAT-60'],       3,  Decimal('1900')),
                (part_map['BAT-74'],       2,  Decimal('2400')),
            ],
        },
        {
            'supplier': suppliers[4],
            'date': date(2026, 5, 20),
            'items': [
                (part_map['TIE-ROD'],      6,  Decimal('160')),
                (part_map['FIL-FUL-001'],  8,  Decimal('150')),
                (part_map['BAT-60'],       2,  Decimal('1950')),
            ],
        },
    ]

    for pd in purchases_data:
        order_date = make_aware(pd['date'])
        gen_num = PurchaseOrder.generate_order_number(COMPANY_ID)

        po = PurchaseOrder.objects.create(
            order_number=gen_num,
            supplier=pd['supplier'],
            status=PurchaseOrder.Status.ORDERED,
            created_by=purchaser,
            company=company,
        )
        PurchaseOrder.objects.filter(pk=po.pk).update(created_at=order_date)
        po.refresh_from_db()

        items_batch: list[tuple[PurchaseOrderItem, Decimal]] = []
        for part, qty, price in pd['items']:
            item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                part=part,
                quantity_ordered=qty,
                unit_price=price,
            )
            items_batch.append((item, qty))

        po = PurchaseOrderService.receive_items(po, items_batch)
        total = po.total_amount
        print(f'  [OK] {po.order_number} ({pd["supplier"].name}) — {pd["date"]} — {total} грн ({len(items_batch)} поз.)')

    total_pos = PurchaseOrder.objects.filter(company=company).count()
    print(f'  [OK] Всього закупівель: {total_pos}')


# =====================================================================
# 5. ЗАМОВЛЕННЯ-НАРЯДИ
# =====================================================================
def create_work_orders(vehicles: list[Vehicle], parts: list[Part], employees: list[Employee]):
    print('\n=== 5. Створення замовлень-нарядів ===')
    company = Company.objects.get(pk=COMPANY_ID)
    admin = next(e for e in employees if e.has_role('admin'))
    mechanic1 = next(e for e in employees if e.user.username == 'mechanic1')
    mechanic2 = next(e for e in employees if e.user.username == 'mechanic2')

    wt: dict[str, WorkType] = {w.name: w for w in WorkType.objects.filter(company=company)}
    part_map: dict[str, Part] = {p.part_number: p for p in parts}

    def get_lot(part: Part) -> PartLot | None:
        return PartLot.objects.filter(
            part=part, company=company,
            quantity__gt=F('quantity_used'),
        ).order_by('created_at').first()

    orders_data: list[dict[str, Any]] = [
        # ============ КВІТЕНЬ ============
        {
            'vehicle_idx': 0, 'date': date(2026, 4, 3),
            'status': WorkOrder.Status.COMPLETED, 'mileage': 124500,
            'notes': 'Планове ТО після 120 000 км',
            'services': [
                ('Комплексне ТО', 3.0, Decimal('800'), 'mechanic1'),
                ('Заміна моторної оливи', 0.5, Decimal('200'), 'mechanic1'),
            ],
            'parts': [
                (part_map['OIL-5W40-4'], 1, Decimal('1200')),
                (part_map['FIL-OIL-001'], 1, Decimal('150')),
                (part_map['FIL-AIR-001'], 1, Decimal('200')),
                (part_map['FIL-CAB-001'], 1, Decimal('180')),
            ],
        },
        {
            'vehicle_idx': 1, 'date': date(2026, 4, 5),
            'status': WorkOrder.Status.COMPLETED, 'mileage': 87000,
            'notes': 'Скрип гальм, заміна колодок та дисків',
            'services': [
                ('Заміна гальмівних колодок', 1.5, Decimal('400'), 'mechanic1'),
                ('Заміна гальмівних дисків', 1.0, Decimal('350'), 'mechanic1'),
            ],
            'parts': [
                (part_map['BRK-PAD-F'], 1, Decimal('650')),
                (part_map['BRK-DIS-F'], 1, Decimal('1500')),
            ],
        },
        {
            'vehicle_idx': 2, 'date': date(2026, 4, 8),
            'status': WorkOrder.Status.COMPLETED, 'mileage': 210300,
            'notes': 'Стук в підвісці, заміна кульових та стійок',
            'services': [
                ('Діагностика ходової частини', 1.0, Decimal('300'), 'mechanic2'),
                ('Заміна кульових опор', 2.0, Decimal('500'), 'mechanic2'),
                ('Заміна стійок стабілізатора', 1.0, Decimal('300'), 'mechanic2'),
                ('Сход-розвал', 1.0, Decimal('400'), 'mechanic2'),
            ],
            'parts': [
                (part_map['BALL-JNT'], 2, Decimal('350')),
                (part_map['STAB-LINK'], 2, Decimal('180')),
            ],
        },
        {
            'vehicle_idx': 3, 'date': date(2026, 4, 12),
            'status': WorkOrder.Status.COMPLETED, 'mileage': 156000,
            'notes': 'Заміна ременя ГРМ та оливи',
            'services': [
                ('Заміна ременя ГРМ', 3.5, Decimal('1200'), 'mechanic1'),
                ('Заміна моторної оливи', 0.5, Decimal('200'), 'mechanic1'),
            ],
            'parts': [
                (part_map['TIM-BELT'], 1, Decimal('1800')),
                (part_map['OIL-5W40-4'], 1, Decimal('1200')),
                (part_map['FIL-OIL-001'], 1, Decimal('150')),
            ],
        },
        {
            'vehicle_idx': 4, 'date': date(2026, 4, 18),
            'status': WorkOrder.Status.COMPLETED, 'mileage': 134200,
            'notes': 'Сезонне ТО + заміна гальмівної рідини',
            'services': [
                ('Комплексне ТО', 2.5, Decimal('800'), 'mechanic1'),
                ('Заміна гальмівної рідини', 0.8, Decimal('250'), 'mechanic1'),
            ],
            'parts': [
                (part_map['OIL-5W30-4'], 1, Decimal('1350')),
                (part_map['FIL-OIL-001'], 1, Decimal('150')),
                (part_map['FIL-AIR-001'], 1, Decimal('200')),
                (part_map['FIL-CAB-001'], 1, Decimal('180')),
                (part_map['BRAKE-DOT4'], 1, Decimal('180')),
            ],
        },
        {
            'vehicle_idx': 5, 'date': date(2026, 4, 22),
            'status': WorkOrder.Status.COMPLETED, 'mileage': 92000,
            'notes': 'Помилка двигуна — діагностика, заміна свічок',
            'services': [
                ("Комп'ютерна діагностика двигуна", 1.0, Decimal('400'), 'mechanic2'),
                ('Заміна свічок запалювання', 1.5, Decimal('350'), 'mechanic2'),
            ],
            'parts': [
                (part_map['SPARK-PL'], 4, Decimal('120')),
            ],
        },
        # ============ ТРАВЕНЬ ============
        {
            'vehicle_idx': 6, 'date': date(2026, 5, 3),
            'status': WorkOrder.Status.COMPLETED, 'mileage': 245000,
            'notes': 'Стук ззаду, течія амортизатора',
            'services': [
                ('Діагностика підвіски', 1.0, Decimal('300'), 'mechanic1'),
                ('Заміна амортизаторів', 2.5, Decimal('700'), 'mechanic1'),
                ('Сход-розвал', 1.0, Decimal('400'), 'mechanic1'),
            ],
            'parts': [
                (part_map['SHP-RR'], 2, Decimal('1100')),
            ],
        },
        {
            'vehicle_idx': 7, 'date': date(2026, 5, 7),
            'status': WorkOrder.Status.COMPLETED, 'mileage': 180500,
            'notes': 'Вібрація при русі, заміна рульових наконечників',
            'services': [
                ('Діагностика ходової частини', 1.0, Decimal('300'), 'mechanic2'),
                ('Заміна рульових наконечників', 1.5, Decimal('400'), 'mechanic2'),
                ('Сход-розвал', 1.0, Decimal('400'), 'mechanic2'),
            ],
            'parts': [
                (part_map['TIE-ROD'], 2, Decimal('280')),
            ],
        },
        {
            'vehicle_idx': 0, 'date': date(2026, 5, 10),
            'status': WorkOrder.Status.COMPLETED, 'mileage': 125800,
            'notes': 'Скрип передньої підвіски, заміна амортизаторів та стійок',
            'services': [
                ('Заміна амортизаторів', 2.5, Decimal('700'), 'mechanic1'),
                ('Заміна стійок стабілізатора', 1.0, Decimal('300'), 'mechanic1'),
                ('Сход-розвал', 1.0, Decimal('400'), 'mechanic1'),
            ],
            'parts': [
                (part_map['SHP-FR'], 2, Decimal('1200')),
                (part_map['STAB-LINK'], 2, Decimal('180')),
            ],
        },
        {
            'vehicle_idx': 1, 'date': date(2026, 5, 14),
            'status': WorkOrder.Status.COMPLETED, 'mileage': 89500,
            'notes': 'Планове ТО + заміна паливного фільтра',
            'services': [
                ('Комплексне ТО', 2.5, Decimal('800'), 'mechanic2'),
                ('Заміна паливного фільтра', 1.0, Decimal('300'), 'mechanic2'),
            ],
            'parts': [
                (part_map['OIL-5W30-4'], 1, Decimal('1350')),
                (part_map['FIL-OIL-001'], 1, Decimal('150')),
                (part_map['FIL-AIR-001'], 1, Decimal('200')),
                (part_map['FIL-CAB-001'], 1, Decimal('180')),
                (part_map['FIL-FUL-001'], 1, Decimal('250')),
            ],
        },
        {
            'vehicle_idx': 3, 'date': date(2026, 5, 19),
            'status': WorkOrder.Status.IN_PROGRESS, 'mileage': 162000,
            'notes': 'Не заводиться — діагностика, заміна АКБ та свічок',
            'services': [
                ("Комп'ютерна діагностика двигуна", 1.0, Decimal('400'), 'mechanic2'),
                ('Заміна акумулятора', 0.5, Decimal('150'), 'mechanic2'),
                ('Заміна свічок запалювання', 1.0, Decimal('350'), 'mechanic2'),
            ],
            'parts': [
                (part_map['BAT-60'], 1, Decimal('2800')),
                (part_map['SPARK-PL'], 4, Decimal('120')),
            ],
        },
        {
            'vehicle_idx': 4, 'date': date(2026, 5, 25),
            'status': WorkOrder.Status.DRAFT, 'mileage': 138000,
            'notes': 'Перед покупкою — комплексна діагностика',
            'services': [
                ("Комп'ютерна діагностика двигуна", 1.0, Decimal('400'), 'mechanic1'),
                ('Діагностика підвіски', 1.0, Decimal('300'), 'mechanic1'),
                ('Діагностика гальмівної системи', 1.0, Decimal('300'), 'mechanic1'),
            ],
            'parts': [],
        },
    ]

    order_count = 0
    for od in orders_data:
        veh = vehicles[od['vehicle_idx']]
        wo_date = make_aware(od['date'])

        wo = WorkOrder.objects.create(
            company=company,
            vehicle=veh,
            created_by=admin,
            status=od['status'],
            notes=od['notes'],
            mileage=od['mileage'],
        )
        WorkOrder.objects.filter(pk=wo.pk).update(created_at=wo_date)
        wo.refresh_from_db()

        # Послуги
        for svc_name, qty, price, mech_username in od['services']:
            if svc_name not in wt:
                print(f'  [WARN] Вид роботи "{svc_name}" не знайдено')
                continue
            mech = mechanic1 if mech_username == 'mechanic1' else mechanic2
            WorkOrderService.objects.create(
                work_order=wo,
                work_type=wt[svc_name],
                quantity=Decimal(str(qty)),
                unit_price=price,
                employee=mech,
                description=svc_name,
            )

        # Запчастини
        for part, qty, price in od['parts']:
            lot = get_lot(part)
            wop = WorkOrderPart.objects.create(
                work_order=wo,
                part=part,
                quantity=qty,
                unit_price=price,
                part_lot=lot,
                purchase_price=lot.purchase_price if lot else None,
            )
            try:
                PartService.decrease_stock(part=part, quantity=qty)
            except ValueError as e:
                print(f'  [WARN] Недостатньо {part.name}: {e}')

            if lot:
                PartLot.objects.filter(pk=lot.pk).update(
                    quantity_used=F('quantity_used') + qty,
                )

        order_count += 1
        total = wo.total_amount
        svc_count = wo.services.count()
        part_count = wo.parts.count()
        print(f'  [OK] Наряд #{wo.pk} — {veh.brand} {veh.model} ({od["date"]}) — {total} грн ({svc_count} послуг, {part_count} запчастин)')

    print(f'  [OK] Всього нарядів: {order_count}')


# =====================================================================
# ПІДСУМОК
# =====================================================================
def print_summary():
    print('\n' + '=' * 60)
    print('   ПІДСУМОК НАПОВНЕННЯ')
    print('=' * 60)
    company = Company.objects.get(pk=COMPANY_ID)

    print(f'  Компанія:          {company.name}')
    print(f'  Співробітники:     {Employee.objects.filter(company=company).count()}')
    print(f'  Види робіт:        {WorkType.objects.filter(company=company).count()}')
    print(f'  Постачальники:     {Supplier.objects.filter(company=company).count()}')
    print(f'  Автомобілі:        {Vehicle.objects.filter(company=company).count()}')
    print(f'  Запчастини:        {Part.objects.filter(company=company).count()}')

    from django.db.models import Sum
    total_stock = Part.objects.filter(company=company).aggregate(
        total=Sum('quantity_on_hand')
    )['total'] or Decimal('0')
    part_lots = PartLot.objects.filter(company=company).count()
    print(f'  Партій (PartLot):  {part_lots}')
    print(f'  Загальний залишок: {total_stock}')

    wo_count = WorkOrder.objects.filter(company=company).count()
    po_count = PurchaseOrder.objects.filter(company=company).count()
    print(f'  Закупівлі:         {po_count}')
    print(f'  Замовлення-наряди: {wo_count}')

    for status_name, status_val in WorkOrder.Status.choices:
        cnt = WorkOrder.objects.filter(company=company, status=status_val).count()
        print(f'    {status_name}: {cnt}')

    all_wo = list(WorkOrder.objects.filter(company=company))
    labor_total = sum(wo.total_labor_cost for wo in all_wo)
    parts_total = sum(wo.total_parts_cost for wo in all_wo)
    print(f'\n  Фінанси:')
    print(f'    Вартість робіт:    {labor_total} грн')
    print(f'    Вартість запчастин: {parts_total} грн')
    print(f'    Загальний дохід:   {labor_total + parts_total} грн')
    print('\n  Наповнення завершено!')


def main():
    print('=' * 60)
    print('   СИМУЛЯЦІЯ 2 МІСЯЦІВ РОБОТИ АВТОСЕРВІСУ')
    print('=' * 60)

    company = Company.objects.get(pk=COMPANY_ID)
    employees = list(Employee.objects.filter(company=company).select_related('user'))

    suppliers = create_suppliers()
    vehicles = create_vehicles()
    parts = create_parts()
    create_purchases(suppliers, parts, employees)
    create_work_orders(vehicles, parts, employees)
    print_summary()


if __name__ == '__main__':
    main()
