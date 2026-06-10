#!/usr/bin/env python
"""
Перевірка поточних налаштувань PostgreSQL та виведення інструкції.

Запуск:
    python scripts/pg_settings.py
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


def main() -> None:
    """Перевіряє налаштування та виводить стан."""
    import django
    django.setup()
    from django.conf import settings

    db = settings.DATABASES['default']
    engine = db['ENGINE']

    print('  Поточні налаштування БД:')
    print(f'  Engine:  {engine}')

    if 'postgresql' in engine:
        print(f'  Host:    {db.get("HOST", "localhost")}')
        print(f'  Port:    {db.get("PORT", "5432")}')
        print(f'  DB Name: {db.get("NAME", "")}')
        print(f'  User:    {db.get("USER", "")}')
        print(f'  SSL:     {"require" if db.get("OPTIONS", {}).get("sslmode") == "require" else "disabled"}')
        print()
        print('  [OK] PostgreSQL активний')
    elif 'sqlite' in engine:
        print(f'  Path:    {db.get("NAME", "")}')
        print()
        print('  [INFO] SQLite активний. Для перемикання на PostgreSQL:')
        print()
        print('  PowerShell:')
        print('    $env:DJANGO_DB_ENGINE = "postgresql"')
        print('    $env:DJANGO_DB_NAME = "autoservice"')
        print('    $env:DJANGO_DB_USER = "autoservice_user"')
        print('    $env:DJANGO_DB_PASSWORD = "your_password"')
        print('    $env:DJANGO_DB_HOST = "localhost"')
        print('    $env:DJANGO_DB_PORT = "5432"')
        print()
        print('  Потiм запустити мiграцiю:')
        print('    python manage.py migrate')
        print()
        print('  Для iмпорту даних (якщо є данi в SQLite):')
        print('    python scripts/migrate_to_postgresql.py')
    else:
        print(f'  [ERROR] Невідомий engine: {engine}')


if __name__ == '__main__':
    main()
