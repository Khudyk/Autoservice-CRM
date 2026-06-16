"""Команда для наповнення бази видами робіт для компанії «Автосервіс Столиця»."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from company.models import Company
from worktypes.models import WorkType

# Типовий перелік робіт для автосервісу з категоріями та описами
WORKTYPES_SEED: list[dict[str, Any]] = [
    # --- ТО (Технічне обслуговування) ---
    {
        'name': 'Заміна моторної оливи',
        'description': 'Злив відпрацьованої оливи, заміна масляного фільтра, заливка нової оливи',
        'category': WorkType.Category.MAINTENANCE,
        'default_price': Decimal('500.00'),
    },
    {
        'name': 'Заміна повітряного фільтра',
        'description': 'Заміна фільтра повітря двигуна',
        'category': WorkType.Category.MAINTENANCE,
        'default_price': Decimal('200.00'),
    },
    {
        'name': 'Заміна салонного фільтра',
        'description': 'Заміна фільтра кондиціонера/опалення',
        'category': WorkType.Category.MAINTENANCE,
        'default_price': Decimal('250.00'),
    },
    {
        'name': 'Заміна паливного фільтра',
        'description': 'Заміна фільтра тонкого очищення палива',
        'category': WorkType.Category.MAINTENANCE,
        'default_price': Decimal('350.00'),
    },
    {
        'name': 'Заміна свічок запалювання',
        'description': 'Діагностика та заміна свічок запалювання',
        'category': WorkType.Category.MAINTENANCE,
        'default_price': Decimal('400.00'),
    },
    {
        'name': 'Заміна ременя ГРМ',
        'description': 'Заміна ременя газорозподільного механізму з роликами',
        'category': WorkType.Category.MAINTENANCE,
        'default_price': Decimal('2500.00'),
    },
    {
        'name': 'Заміна рідини охолодження',
        'description': 'Злив та заливка антифризу/тосолу',
        'category': WorkType.Category.MAINTENANCE,
        'default_price': Decimal('300.00'),
    },
    {
        'name': 'Заміна гальмівної рідини',
        'description': 'Промивка та заміна гальмівної рідини',
        'category': WorkType.Category.MAINTENANCE,
        'default_price': Decimal('350.00'),
    },
    {
        'name': 'Заміна трансмісійної оливи',
        'description': 'Заміна оливи в коробці передач (АКПП/МКПП)',
        'category': WorkType.Category.MAINTENANCE,
        'default_price': Decimal('600.00'),
    },
    {
        'name': 'Комплексне ТО',
        'description': 'Планове технічне обслуговування за регламентом виробника',
        'category': WorkType.Category.MAINTENANCE,
        'default_price': Decimal('3000.00'),
    },

    # --- Діагностика ---
    {
        'name': 'Комп\'ютерна діагностика двигуна',
        'description': 'Зчитування помилок, перевірка параметрів ЕБУ',
        'category': WorkType.Category.DIAGNOSTICS,
        'default_price': Decimal('500.00'),
    },
    {
        'name': 'Діагностика підвіски',
        'description': 'Перевірка стану амортизаторів, важелів, сайлентблоків',
        'category': WorkType.Category.DIAGNOSTICS,
        'default_price': Decimal('400.00'),
    },
    {
        'name': 'Діагностика ходової частини',
        'description': 'Перевірка шарнірів, стійок стабілізатора, рульових наконечників',
        'category': WorkType.Category.DIAGNOSTICS,
        'default_price': Decimal('400.00'),
    },
    {
        'name': 'Діагностика електрообладнання',
        'description': 'Перевірка генератора, стартера, проводки',
        'category': WorkType.Category.DIAGNOSTICS,
        'default_price': Decimal('450.00'),
    },
    {
        'name': 'Діагностика гальмівної системи',
        'description': 'Перевірка гальмівних дисків, колодок, супортів',
        'category': WorkType.Category.DIAGNOSTICS,
        'default_price': Decimal('300.00'),
    },
    {
        'name': 'Діагностика кондиціонера',
        'description': 'Перевірка тиску, герметичності системи',
        'category': WorkType.Category.DIAGNOSTICS,
        'default_price': Decimal('350.00'),
    },

    # --- Ремонт ---
    {
        'name': 'Заміна гальмівних колодок',
        'description': 'Заміна передніх або задніх гальмівних колодок',
        'category': WorkType.Category.REPAIR,
        'default_price': Decimal('800.00'),
    },
    {
        'name': 'Заміна гальмівних дисків',
        'description': 'Заміна передніх або задніх гальмівних дисків',
        'category': WorkType.Category.REPAIR,
        'default_price': Decimal('1200.00'),
    },
    {
        'name': 'Заміна амортизаторів',
        'description': 'Заміна передніх або задніх амортизаторів',
        'category': WorkType.Category.REPAIR,
        'default_price': Decimal('1500.00'),
    },
    {
        'name': 'Заміна кульових опор',
        'description': 'Заміна кульових опор передньої підвіски',
        'category': WorkType.Category.REPAIR,
        'default_price': Decimal('600.00'),
    },
    {
        'name': 'Заміна сайлентблоків',
        'description': 'Заміна сайлентблоків важелів підвіски',
        'category': WorkType.Category.REPAIR,
        'default_price': Decimal('700.00'),
    },
    {
        'name': 'Заміна стійок стабілізатора',
        'description': 'Заміна стійок стабілізатора поперечної стійкості',
        'category': WorkType.Category.REPAIR,
        'default_price': Decimal('500.00'),
    },
    {
        'name': 'Заміна рульових наконечників',
        'description': 'Заміна наконечників рульової трапеції',
        'category': WorkType.Category.REPAIR,
        'default_price': Decimal('500.00'),
    },
    {
        'name': 'Ремонт двигуна',
        'description': 'Капітальний або поточний ремонт двигуна',
        'category': WorkType.Category.REPAIR,
        'default_price': Decimal('5000.00'),
    },
    {
        'name': 'Заміна зчеплення',
        'description': 'Заміна комплекту зчеплення (диск, кошик, вижимний)',
        'category': WorkType.Category.REPAIR,
        'default_price': Decimal('2500.00'),
    },
    {
        'name': 'Заміна глушника',
        'description': 'Заміна елементів випускної системи',
        'category': WorkType.Category.REPAIR,
        'default_price': Decimal('800.00'),
    },
    {
        'name': 'Ремонт системи охолодження',
        'description': 'Заміна термостата, помпи, радіатора',
        'category': WorkType.Category.REPAIR,
        'default_price': Decimal('1200.00'),
    },

    # --- Електрика ---
    {
        'name': 'Заміна акумулятора',
        'description': 'Діагностика та заміна АКБ',
        'category': WorkType.Category.ELECTRICAL,
        'default_price': Decimal('300.00'),
    },
    {
        'name': 'Заміна генератора',
        'description': 'Діагностика та заміна генератора',
        'category': WorkType.Category.ELECTRICAL,
        'default_price': Decimal('1500.00'),
    },
    {
        'name': 'Заміна стартера',
        'description': 'Діагностика та заміна стартера',
        'category': WorkType.Category.ELECTRICAL,
        'default_price': Decimal('1000.00'),
    },
    {
        'name': 'Ремонт електропроводки',
        'description': 'Ремонт або заміна джгутів проводів',
        'category': WorkType.Category.ELECTRICAL,
        'default_price': Decimal('800.00'),
    },
    {
        'name': 'Заміна лампочок',
        'description': 'Заміна ламп головного світла, габаритів, салону',
        'category': WorkType.Category.ELECTRICAL,
        'default_price': Decimal('100.00'),
    },
    {
        'name': 'Діагностика та ремонт кондиціонера',
        'description': 'Діагностика, заправка, ремонт системи кондиціонування',
        'category': WorkType.Category.ELECTRICAL,
        'default_price': Decimal('800.00'),
    },

    # --- Кузовні роботи ---
    {
        'name': 'Рихтовка та фарбування',
        'description': 'Усунення вм\'ятин та фарбування елементів кузова',
        'category': WorkType.Category.BODYWORK,
        'default_price': Decimal('3000.00'),
    },
    {
        'name': 'Локальне фарбування',
        'description': 'Фарбування окремої деталі з переходом',
        'category': WorkType.Category.BODYWORK,
        'default_price': Decimal('2000.00'),
    },
    {
        'name': 'Полірування кузова',
        'description': 'Абразивне або захисне полірування лакофарбового покриття',
        'category': WorkType.Category.BODYWORK,
        'default_price': Decimal('1500.00'),
    },
    {
        'name': 'Заміна лобового скла',
        'description': 'Демонтаж та встановлення нового лобового скла',
        'category': WorkType.Category.BODYWORK,
        'default_price': Decimal('1500.00'),
    },
    {
        'name': 'Антикорозійна обробка',
        'description': 'Обробка днища та прихованих порожнин антикором',
        'category': WorkType.Category.BODYWORK,
        'default_price': Decimal('2000.00'),
    },

    # --- Шиномонтаж ---
    {
        'name': 'Сезонна заміна шин',
        'description': 'Перевзуття коліс (комплект)',
        'category': WorkType.Category.TYRE,
        'default_price': Decimal('800.00'),
    },
    {
        'name': 'Балансування коліс',
        'description': 'Балансування шин на стенді',
        'category': WorkType.Category.TYRE,
        'default_price': Decimal('400.00'),
    },
    {
        'name': 'Ремонт проколу шини',
        'description': 'Вулканізація або встановлення джгута',
        'category': WorkType.Category.TYRE,
        'default_price': Decimal('300.00'),
    },
    {
        'name': 'Сход-розвал',
        'description': 'Регулювання кутів встановлення коліс (3D)',
        'category': WorkType.Category.TYRE,
        'default_price': Decimal('600.00'),
    },
    {
        'name': 'Встановлення датчиків тиску',
        'description': 'Встановлення та синхронізація датчиків TPMS',
        'category': WorkType.Category.TYRE,
        'default_price': Decimal('500.00'),
    },

    # --- Детейлінг ---
    {
        'name': 'Хімчистка салону',
        'description': 'Комплексна чистка салону з мийкою',
        'category': WorkType.Category.DETAILING,
        'default_price': Decimal('2000.00'),
    },
    {
        'name': 'Мийка автомобіля',
        'description': 'Зовнішня мийка авто з шампунем',
        'category': WorkType.Category.DETAILING,
        'default_price': Decimal('500.00'),
    },
    {
        'name': 'Чистка двигуна',
        'description': 'Мийка двигуна та моторного відсіку',
        'category': WorkType.Category.DETAILING,
        'default_price': Decimal('600.00'),
    },
    {
        'name': 'Нанесення керамічного покриття',
        'description': 'Захисне покриття кузова рідкою керамікою',
        'category': WorkType.Category.DETAILING,
        'default_price': Decimal('5000.00'),
    },
    {
        'name': 'Тонування скла',
        'description': 'Тонування скла плівкою',
        'category': WorkType.Category.DETAILING,
        'default_price': Decimal('2000.00'),
    },

    # --- Інше ---
    {
        'name': 'Евакуація автомобіля',
        'description': 'Транспортування несправного авто на сервіс',
        'category': WorkType.Category.OTHER,
        'default_price': Decimal('1500.00'),
    },
    {
        'name': 'Заміна ключів та чіпів',
        'description': 'Виготовлення та програмування ключів',
        'category': WorkType.Category.OTHER,
        'default_price': Decimal('1200.00'),
    },
    {
        'name': 'Консультація',
        'description': 'Безкоштовна консультація фахівця',
        'category': WorkType.Category.OTHER,
        'default_price': Decimal('0.00'),
    },
]


class Command(BaseCommand):
    """Наповнює базу видами робіт для «Автосервіс Столиця»."""

    help = 'Створює типовий перелік робіт для компанії «Автосервіс Столиця»'

    def add_arguments(self, parser: CommandParser) -> None:
        """Додає аргументи команди.

        Args:
            parser: Парсер аргументів.
        """
        parser.add_argument(
            '--company',
            type=int,
            default=None,
            help='ID компанії (за замовчуванням — «Автосервіс Столиця»)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Оновити існуючі записи (за замовчуванням пропускає)',
        )

    def handle(self, *args: Any, **options: Any) -> str:
        """Виконує наповнення бази видами робіт.

        Returns:
            Повідомлення про результат.
        """
        company_id: int | None = options.get('company')
        force: bool = options.get('force', False)

        if company_id:
            try:
                company = Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                self.stderr.write(f'Компанію з ID {company_id} не знайдено.')
                return
        else:
            company = Company.objects.filter(name='Автосервіс Столиця').first()
            if not company:
                self.stderr.write(
                    'Компанію «Автосервіс Столиця» не знайдено. '
                    'Вкажіть ID через --company.',
                )
                return

        created_count: int = 0
        skipped_count: int = 0
        updated_count: int = 0

        for data in WORKTYPES_SEED:
            name: str = data['name']
            worktype, was_created = WorkType.objects.get_or_create(
                name=name,
                company=company,
                defaults={
                    'description': data.get('description', ''),
                    'category': data.get('category', WorkType.Category.OTHER),
                    'default_price': data.get('default_price', Decimal('0.00')),
                    'is_active': True,
                },
            )
            if was_created:
                created_count += 1
            elif force:
                # Оновлюємо існуючий запис
                worktype.description = data.get('description', '')
                worktype.category = data.get('category', WorkType.Category.OTHER)
                worktype.default_price = data.get('default_price', Decimal('0.00'))
                worktype.is_active = True
                worktype.save()
                updated_count += 1
            else:
                skipped_count += 1

        parts: list[str] = []
        if created_count:
            parts.append(f'створено {created_count}')
        if updated_count:
            parts.append(f'оновлено {updated_count}')
        if skipped_count:
            parts.append(f'пропущено {skipped_count}')
        result: str = f'{", ".join(parts)} видів робіт для «{company.name}»'

        if created_count or updated_count:
            self.stdout.write(self.style.SUCCESS(result))
        else:
            self.stdout.write(result)

        return result
