#!/usr/bin/env python
"""
Скрипт міграції даних з SQLite в PostgreSQL для Autoservice CRM.

Використання:
    1. Встанови PostgreSQL та створи базу даних:
       createdb autoservice
       createuser autoservice_user -P
       psql -d autoservice -c "GRANT ALL ON SCHEMA public TO autoservice_user;"

    2. Встанови змінні оточення для PostgreSQL:
       $env:DJANGO_DB_ENGINE = 'postgresql'
       $env:DJANGO_DB_NAME = 'autoservice'
       $env:DJANGO_DB_USER = 'autoservice_user'
       $env:DJANGO_DB_PASSWORD = 'your_password'
       $env:DJANGO_DB_HOST = 'localhost'
       $env:DJANGO_DB_PORT = '5432'

    3. Запусти міграцію:
       python scripts/migrate_to_postgresql.py

    АБО виконай вручну кроки, описані нижче.

Важливо: Перед міграцією переконайся, що всі міграції застосовано до SQLite,
а сам SQLite-сервер не запущено (щоб уникнути стану гонки).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FIXTURE_FILE = BASE_DIR / 'data_dump.json'


def step(msg: str) -> None:
    """Друкує крок з форматуванням."""
    print(f'\n{"=" * 60}')
    print(f'  {msg}')
    print(f'{"=" * 60}')


def run(cmd: list[str], cwd: Path | None = None) -> None:
    """Запускає команду та виводить результат."""
    result = subprocess.run(cmd, cwd=cwd or BASE_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print(f'[ERROR] {result.stderr}')
        sys.exit(result.returncode)
    if result.stdout:
        print(result.stdout[:2000])
    if result.stderr:
        print(f'[STDERR] {result.stderr[:1000]}')


def check_postgresql_connection() -> bool:
    """Перевіряє, чи доступний PostgreSQL."""
    try:
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        # Тимчасово вмикаємо PostgreSQL
        os.environ['DJANGO_DB_ENGINE'] = 'postgresql'
        django.setup()
        from django.db import connection
        connection.ensure_connection()
        connection.close()
        return True
    except Exception as e:
        print(f'  PostgreSQL недоступний: {e}')
        return False


def main() -> None:
    """Головна функція міграції."""
    print()
    print('  === Міграція Autoservice CRM: SQLite -> PostgreSQL ===')

    # Перевірка, чи задано PostgreSQL
    if os.getenv('DJANGO_DB_ENGINE') != 'postgresql':
        print()
        print('  [УВАГА] Змінна DJANGO_DB_ENGINE не встановлена в "postgresql".')
        print()
        print('  Встановіть змінні оточення:')
        print('    $env:DJANGO_DB_ENGINE = "postgresql"')
        print('    $env:DJANGO_DB_NAME = "autoservice"')
        print('    $env:DJANGO_DB_USER = "autoservice_user"')
        print('    $env:DJANGO_DB_PASSWORD = "your_password"')
        print('    $env:DJANGO_DB_HOST = "localhost"')
        print('    $env:DJANGO_DB_PORT = "5432"')
        print()
        sys.exit(1)

    # Крок 1: Експорт даних з SQLite
    step('Крок 1: Експорт даних з SQLite у JSON (dumpdata)')
    print('  Використовуємо поточну SQLite БД...')
    
    # Тимчасово перемикаємось на SQLite для дампу
    current_engine = os.environ.pop('DJANGO_DB_ENGINE', None)
    run([
        sys.executable, 'manage.py', 'dumpdata',
        '--exclude=contenttypes',
        '--exclude=auth.permission',
        '--exclude=admin.logentry',
        '--exclude=sessions',
        '--natural-foreign',
        '--indent=2',
        '--output', str(FIXTURE_FILE),
    ])
    print(f'  ✅ Дані експортовано у {FIXTURE_FILE}')

    # Відновлюємо змінну для PostgreSQL
    if current_engine:
        os.environ['DJANGO_DB_ENGINE'] = current_engine

    # Крок 2: Перевірка PostgreSQL
    step('Крок 2: Перевірка підключення до PostgreSQL')
    if not check_postgresql_connection():
        print('  ❌ Не вдалося підключитись до PostgreSQL.')
        print('  Переконайтеся, що PostgreSQL запущено та змінні оточення вказано правильно.')
        sys.exit(1)
    print('  ✅ Підключення до PostgreSQL успішне')

    # Крок 3: Застосування міграцій до PostgreSQL
    step('Крок 3: Застосування міграцій до PostgreSQL')
    run([sys.executable, 'manage.py', 'migrate', '--run-syncdb'])
    print('  ✅ Міграції застосовано до PostgreSQL')

    # Крок 4: Імпорт даних
    step('Крок 4: Імпорт даних у PostgreSQL')
    run([sys.executable, 'manage.py', 'loaddata', str(FIXTURE_FILE)])
    print('  ✅ Дані імпортовано в PostgreSQL')

    # Крок 5: Перевірка
    step('Крок 5: Перевірка цілісності даних')
    run([sys.executable, 'manage.py', 'check'])
    print('  ✅ Перевірка пройдена')

    # Крок 6: Очищення
    step('Крок 6: Очищення')
    if FIXTURE_FILE.exists():
        FIXTURE_FILE.unlink()
        print(f'  ✅ Тимчасовий файл {FIXTURE_FILE} видалено')

    print()
    print('  === Міграція завершена успішно! ===')
    print('  Тепер база даних працює на PostgreSQL.')
    print()
    print('  Для повернення до SQLite:')
    print('    Remove-Item Env:DJANGO_DB_ENGINE')
    print()


if __name__ == '__main__':
    main()
