# AGENTS.md — Autoservice CRM

Django 6.0.3 / SQLite / Bootstrap 5.3 CDN / pytest 8.x.

## Команди

| Команда | Призначення |
|---|---|
| `python manage.py runserver` | Dev-сервер |
| `pytest` | Всі тести (не `manage.py test`) |
| `pytest <dir>/tests/ -v` | Один додаток |
| `pytest <pkg>::<class>::<method> -v` | Один тест |
| `python manage.py check` | Перевірка конфігурації |
| `python manage.py makemigrations && python manage.py migrate` | Міграції |
| `python manage.py startapp <name>` | Новий додаток |
| `python manage.py seed_roles` | Наповнити довідник ролей (обов'язково після міграцій) |
| `python manage.py seed_worktypes` | Наповнити довідник видів робіт |
| `.\scripts\test-and-commit.ps1` | Запустити тести + при успіху створити Git-коміт |
| `.\scripts\test-and-commit.ps1 -Message "опис"` | Тести + коміт з власним повідомленням |
| `.\scripts\test-and-commit.ps1 -Push` | Тести + коміт + git push (якщо налаштовано remote) |

## Налаштування

- `DJANGO_SETTINGS_MODULE=config.settings` (файл у `config/settings.py`)
- Змінні оточення: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`
- Без `DJANGO_SECRET_KEY` у production — `ImproperlyConfigured`

## Архітектура

- **8 додатків** (порядок в `INSTALLED_APPS`): `company`, `accounts`, `vehicles`, `worktypes`, `suppliers`, `parts`, `purchases`, `workorders`
- **Multi-tenant**: кожен запис має `company` FK. Views фільтрують через `filter_queryset_by_company()` (`accounts.utils`). `is_staff`/`is_superuser` бачать усе.
- **FBVs тільки**, всі з `@login_required`. Тонкі views, бізнес-логіка в `services.py` (accounts, parts, purchases, workorders) або `@property` моделей.
- **Атомарність**: write-операції в `@transaction.atomic`. Залишки через `F()` (race condition захист).
- **100% Type Hinting**.
- **Навігація**: Лівий сайдбар (260px). `config/context_processors.py` формує `nav_main` / `nav_admin` через `NavItem` dataclass з permission checks. На мобільних пристроях сайдбар згортається через кнопку-гамбургер.

## Центральні утиліти (`accounts/utils.py`)

- `filter_queryset_by_company(request, qs, field='company')` — фільтрація за компанією
- `prepare_list_context(request, qs)` → `(qs, companies, selected_company)` — фільтр + компанії
- `paginate_queryset(request, qs, per_page=25)` → `Page`
- `is_admin_user(...)`, `has_workorder_permission(...)`, `get_user_company(...)`
- Employee-ролі: `admin`/`director` → повний доступ; `manager` → workorders; `purchaser`/`storekeeper` → закупівлі

## Тестування

- `conftest.py` у корені — фікстура `roles` (7 ролей). `@pytest.mark.django_db` для БД-тестів.
- **НЕ запускай pytest автоматично** після змін у коді. Тільки `python manage.py check`.
- Фікстури в `conftest.py` кожного додатку, ланцюжок: `company` → `user` → `employee` → ...
- Тести в `tests/test_models.py`, `tests/test_services.py`, `tests/test_views.py`. AAA pattern.

## Шаблони

- Базовий: `templates/base.html` (Bootstrap 5.3 CDN)
- Стилі: `static/css/style.css`, JS: `static/js/app.js`
- Bootstrap-класи в `attrs={'class': 'form-control'}`

## Важливі нюанси

- `RULES.md` **застарілий** — згадує `autoservice/settings.py`, якого немає. Не покладатись.
- **Employee тільки для адмінів**: accounts views перевіряють `is_admin_user()`, 403 для звичайних.
- Employee ↔ User через `OneToOneField`. Створення тільки через `EmployeeForm`.
- `PartLot` створюються автоматично при оприбуткуванні закупівлі.
- Видалення `WorkOrder` повертає запчастини на склад.
