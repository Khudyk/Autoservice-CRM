# Правила проекту Autoservice
##
- заборонено вибаляту данні з бази данних 
## Технології
- Django 6.0.3
- bootstrap 5.3.8
- SQLite (база даних)
- Python

## Структура проекту
- `autoservice/` - основний Django проект
- `manage.py` - файл керування Django

## Конвенції коду
- Python PEP 8
- Назви моделей - PascalCase
- Назви представлень - snake_case
- HTML шаблони - snake_case

## Запуск проекту
- запуск проекту відбуваєнься в новому вікні
```bash
Start-Process python -ArgumentList "manage.py runserver" -WindowStyle Normal
```
## рестарт  проекту
- запуск проекту відбуваєнься в новому вікні
```bash
Stop-Process -Name python -Force
Start-Process python -ArgumentList "manage.py runserver" -WindowStyle Normal
```

## Міграції
```bash
python manage.py makemigrations
python manage.py migrate
```

## Створення додатку
```bash
python manage.py startapp <app_name>
```

## Рекомендації
- Все що ви відповідаєш має українською 
- Використовувати Bootstrap для HTML шаблонів
- Додавати нові додатки в INSTALLED_APPS (settings.py)
- Реєструвати моделі в admin.py
