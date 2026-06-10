# Аудит безпеки сторінок — Autoservice CRM

Дата: 2026-06-02

## Загальний рівень безпеки: **Задовільний**

Проєкт демонструє добру обізнаність у питаннях безпеки: застосовано multi-tenant ізоляцію, CSRF-захист, налаштовано безпечні cookie, HSTS, Content-Security-Policy (у продакшені), захист від brute-force через django-axes, атомарні операції з F() виразами для захисту від race conditions, а також логування подій безпеки.

**Основні проблеми:**
1. **Відсутність рольової перевірки в Vehicles** — будь-який аутентифікований користувач може створювати, редагувати та видаляти автомобілі.
2. **WorkOrder list/detail без перевірки ролі** — будь-який аутентифікований користувач бачить усі наряди своєї компанії (хоча редагування захищене).
3. **Company update без multi-tenant фільтрації** — хоча доступ обмежений адміністраторами, відсутній ilter_queryset_by_company().
4. **Відсутність захисту від CSRF для окремих POST-ендпоінтів не виявлено** — усі форми використовують Django CSRF middleware.
5. **Rate limiting активний лише в продакшені** — у режимі DEBUG захист від перебору паролів відсутній.

---

## Матриця доступу «Роль → Сторінка»

| # | Сторінка | URL | admin | director | manager | master | accountant | purchaser | storekeeper |
|---|----------|-----|-------|----------|---------|--------|------------|-----------|-------------|
| 1 | Головна (дашборд) | / | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 2 | Логін | /employees/login/ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3 | Логаут | /employees/logout/ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4 | Список співробітників | /employees/ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 5 | Створення співробітника | /employees/create/ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 6 | Редагування співробітника | /employees/<pk>/edit/ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 7 | Видалення співробітника | /employees/<pk>/delete/ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 8 | Список компаній | /companies/ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 9 | Створення компанії | /companies/create/ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 10 | Редагування компанії | /companies/<pk>/edit/ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 11 | Список автомобілів | /vehicles/ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 12 | Створення автомобіля | /vehicles/create/ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 13 | Редагування автомобіля | /vehicles/<pk>/edit/ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 14 | Видалення автомобіля | /vehicles/<pk>/delete/ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 15 | Список видів робіт | /worktypes/ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 16 | Створення виду роботи | /worktypes/create/ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 17 | Редагування виду роботи | /worktypes/<pk>/edit/ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 18 | Видалення виду роботи | /worktypes/<pk>/delete/ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 19 | Список постачальників | /suppliers/ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 20 | Створення постачальника | /suppliers/create/ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 21 | Редагування постачальника | /suppliers/<pk>/edit/ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 22 | Видалення постачальника | /suppliers/<pk>/delete/ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 23 | Список запчастин | /parts/ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 24 | Створення запчастини | /parts/create/ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 25 | Редагування запчастини | /parts/<pk>/edit/ | ✅ | ✅ | ⚠️️ | ❌ | ❌ | ⚠️️ | ❌ |
| 26 | Видалення запчастини | /parts/<pk>/delete/ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 27 | Список закупівель | /purchases/ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| 28 | Створення закупівлі | /purchases/create/ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| 29 | Деталі закупівлі | /purchases/<pk>/ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| 30 | Редагування закупівлі | /purchases/<pk>/edit/ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| 31 | Відправлення закупівлі | /purchases/<pk>/submit/ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| 32 | Оприбуткування закупівлі | /purchases/<pk>/receive/ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| 33 | Скасування закупівлі | /purchases/<pk>/cancel/ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| 34 | Видалення закупівлі | /purchases/<pk>/delete/ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| 35 | Список нарядів | /workorders/ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 36 | Деталі наряду | /workorders/<pk>/ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 37 | Створення наряду | /workorders/create/ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 38 | Редагування наряду | /workorders/<pk>/edit/ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 39 | Видалення наряду | /workorders/<pk>/delete/ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

**Умовні позначення:**
- ✅ — Повний доступ
- ⚠️ — Обмежений доступ (тільки редагування продажної ціни)
- ❌ — Немає доступу (403 або перенаправлення)

---

## Детальний опис кожної сторінки

### 1. Головна сторінка (Dashboard)
- **URL**: /
- **Методи**: GET
- **Додаток**: config
- **View-функція**: index
- **Декоратори**: відсутні
- **Перевірка ролі**: відсутня — анонімні користувачі бачать спрощену версію
- **Multi-tenant**: Так — фільтрація за company_id__in=company_ids
- **Доступні ролі**: Усі (включно з анонімними)
- **Опис**: Відображає статистику по компанії: кількість співробітників, автомобілів, запчастин, постачальників, активні замовлення та наряди.
- **Ризики**: Низький — лише агреговані дані, без чутливої інформації
- **Рекомендації**: Немає

---

### 2. Логін
- **URL**: /employees/login/
- **Методи**: GET, POST
- **Додаток**: accounts (Django uth_views.LoginView)
- **View-функція**: django.contrib.auth.views.LoginView
- **Декоратори**: відсутні (стандартний Django)
- **Перевірка ролі**: не застосовується
- **Multi-tenant**: Ні
- **Доступні ролі**: Усі (включно з анонімними)
- **Опис**: Форма входу в систему. Використовує стандартний Django LoginView з кастомним шаблоном egistration/login.html.
- **Ризики**:
  - У режимі DEBUG відсутній захист від brute-force (django-axes вимкнено)
  - Немає обмеження швидкості (rate limiting) на рівні додатку
- **Рекомендації**:
  - Розглянути можливість додавання reCAPTCHA або іншого захисту від автоматизованих атак навіть у режимі DEBUG

---

### 3. Логаут
- **URL**: /employees/logout/
- **Методи**: GET (Django LogoutView)
- **Додаток**: accounts
- **View-функція**: django.contrib.auth.views.LogoutView
- **Декоратори**: відсутні
- **Перевірка ролі**: не застосовується
- **Multi-tenant**: Ні
- **Доступні ролі**: Усі аутентифіковані
- **Опис**: Виконує вихід із системи та перенаправляє на сторінку логіну.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 4. Список співробітників
- **URL**: /employees/
- **Методи**: GET
- **Додаток**: accounts
- **View-функція**: employee_list
- **Декоратори**: @login_required
- **Перевірка ролі**: has_catalog_edit_permission() → 403 (лише admin/director)
- **Multi-tenant**: Так — prepare_list_context()
- **Доступні ролі**: admin (staff/superuser), director, admin (роль)
- **Опис**: Відображає список усіх співробітників компанії з можливістю пагінації. Для адміністраторів — фільтр за компанією.
- **Ризики**: Немає — належна перевірка ролі
- **Рекомендації**: Немає

---

### 5. Створення співробітника
- **URL**: /employees/create/
- **Методи**: GET, POST
- **Додаток**: accounts
- **View-функція**: employee_create
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_catalog_edit_permission() → 403; додаткова перевірка is_superuser або hasattr(user, 'employee')
- **Multi-tenant**: Так — EmployeeForm обмежує компанію
- **Доступні ролі**: admin (staff/superuser), director, admin (роль)
- **Опис**: Форма створення нового співробітника разом з обліковим записом User.
- **Ризики**:
  - Пароль передається у формі (стандартна практика, але потребує HTTPS)
  - При створенні без пароля генерується випадковий через User.objects.make_random_password()
- **Рекомендації**: Немає

---

### 6. Редагування співробітника
- **URL**: /employees/<pk>/edit/
- **Методи**: GET, POST
- **Додаток**: accounts
- **View-функція**: employee_update
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_catalog_edit_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: admin (staff/superuser), director, admin (роль)
- **Опис**: Форма редагування даних співробітника та його облікового запису.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 7. Видалення співробітника
- **URL**: /employees/<pk>/delete/
- **Методи**: GET, POST
- **Додаток**: accounts
- **View-функція**: employee_delete
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_catalog_edit_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: admin (staff/superuser), director, admin (роль)
- **Опис**: Сторінка підтвердження видалення співробітника.
- **Ризики**:
  - Видалення Employee не видаляє User (каскадне видалення через OneToOneField з on_delete=CASCADE — User видаляється разом з Employee). Це може бути небажаною поведінкою.
- **Рекомендації**:
  - Розглянути можливість деактивації користувача замість видалення

---

### 8. Список компаній
- **URL**: /companies/
- **Методи**: GET
- **Додаток**: company
- **View-функція**: company_list
- **Декоратори**: @login_required
- **Перевірка ролі**: відсутня (крім @login_required)
- **Multi-tenant**: Так — _get_visible_companies() обмежує до своєї компанії
- **Доступні ролі**: Усі аутентифіковані
- **Опис**: Список компаній. Адміністратори бачать усі компанії, звичайні користувачі — тільки свою.
- **Ризики**: Низький — користувач бачить лише свою компанію
- **Рекомендації**: Немає

---

### 9. Створення компанії
- **URL**: /companies/create/
- **Методи**: GET, POST
- **Додаток**: company
- **View-функція**: company_create
- **Декоратори**: @login_required
- **Перевірка ролі**: is_admin_user() → redirect (лише staff/superuser)
- **Multi-tenant**: Н/Д (створення нової компанії)
- **Доступні ролі**: **admin (staff/superuser) тільки**
- **Опис**: Форма створення нової компанії.
- **Ризики**: Низький — доступно лише staff/superuser
- **Рекомендації**:
  - Замість edirect бажано використовувати aise PermissionDenied() для однакової поведінки з іншими обмеженнями доступу

---

### 10. Редагування компанії
- **URL**: /companies/<pk>/edit/
- **Методи**: GET, POST
- **Додаток**: company
- **View-функція**: company_update
- **Декоратори**: @login_required
- **Перевірка ролі**: is_admin_user() → redirect (лише staff/superuser)
- **Multi-tenant**: **НІ** — get_object_or_404(Company, pk=pk) без фільтрації за компанією
- **Доступні ролі**: **admin (staff/superuser) тільки**
- **Опис**: Форма редагування даних компанії.
- **Ризики**:
  - Хоча доступ мають лише staff/superuser, **відсутній ilter_queryset_by_company()**. Адміністратор, який не належить до жодної компанії (що технічно можливо), може редагувати будь-яку компанію.
- **Рекомендації**:
  - Додати ilter_queryset_by_company() для консистентності, хоча ризик низький через admin-only доступ

---

### 11. Список автомобілів
- **URL**: /vehicles/
- **Методи**: GET
- **Додаток**: vehicles
- **View-функція**: ehicle_list
- **Декоратори**: @login_required
- **Перевірка ролі**: відсутня
- **Multi-tenant**: Так — prepare_list_context()
- **Доступні ролі**: **Усі аутентифіковані**
- **Опис**: Список автомобілів з пошуком за VIN-кодом та пагінацією.
- **Ризики**: Низький — multi-tenant ізоляція працює
- **Рекомендації**: Немає

---

### 12. Створення автомобіля ⚠️ [P2-Medium]
- **URL**: /vehicles/create/
- **Методи**: GET, POST
- **Додаток**: vehicles
- **View-функція**: ehicle_create
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: **ВІДСУТНЯ** — тільки @login_required
- **Multi-tenant**: Так — для не-admin поле company блокується
- **Доступні ролі**: **Усі аутентифіковані**
- **Опис**: Форма створення нового автомобіля. Будь-який співробітник (навіть майстер або бухгалтер) може додати автомобіль.
- **Ризики**: 🟡 **Середній** — відсутність рольової перевірки. Будь-який співробітник може створювати автомобілі без обмежень.
- **Рекомендації**:
  - Додати перевірку ролі, наприклад, has_catalog_edit_permission() або хоча б обмежити створення для manager/director/admin

---

### 13. Редагування автомобіля ⚠️ [P2-Medium]
- **URL**: /vehicles/<pk>/edit/
- **Методи**: GET, POST
- **Додаток**: vehicles
- **View-функція**: ehicle_update
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: **ВІДСУТНЯ** — тільки @login_required
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: **Усі аутентифіковані** (в межах своєї компанії)
- **Опис**: Форма редагування автомобіля. Якщо на автомобіль є наряди — повертає 409 Conflict.
- **Ризики**: 🟡 **Середній** — відсутність рольової перевірки. Будь-який співробітник може редагувати автомобілі.
- **Рекомендації**:
  - Додати перевірку ролі аналогічно іншим CRUD-сторінкам

---

### 14. Видалення автомобіля ⚠️ [P2-Medium]
- **URL**: /vehicles/<pk>/delete/
- **Методи**: GET, POST
- **Додаток**: vehicles
- **View-функція**: ehicle_delete
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: **ВІДСУТНЯ** — тільки @login_required
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: **Усі аутентифіковані** (в межах своєї компанії)
- **Опис**: Сторінка підтвердження видалення автомобіля. Якщо є наряди — 409 Conflict.
- **Ризики**: 🟡 **Середній** — будь-який співробітник може видалити автомобіль, що призведе до втрати даних.
- **Рекомендації**:
  - Додати перевірку has_catalog_edit_permission() або аналогічну

---

### 15. Список видів робіт
- **URL**: /worktypes/
- **Методи**: GET
- **Додаток**: worktypes
- **View-функція**: worktype_list
- **Декоратори**: @login_required
- **Перевірка ролі**: відсутня (читання), has_catalog_edit_permission() передається в шаблон як can_edit
- **Multi-tenant**: Так — prepare_list_context()
- **Доступні ролі**: Усі аутентифіковані (читання); admin/director (редагування через UI)
- **Опис**: Список видів робіт з пагінацією. Кнопки редагування/видалення показуються лише для can_edit=True.
- **Ризики**: Низький — multi-tenant ізоляція працює, редагування захищене на рівні окремих view
- **Рекомендації**: Немає

---

### 16. Створення виду роботи
- **URL**: /worktypes/create/
- **Методи**: GET, POST
- **Додаток**: worktypes
- **View-функція**: worktype_create
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_catalog_edit_permission() → 403
- **Multi-tenant**: Так — форма обмежує компанію для не-admin
- **Доступні ролі**: admin (staff/superuser), director, admin (роль)
- **Опис**: Форма створення нового виду роботи.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 17. Редагування виду роботи
- **URL**: /worktypes/<pk>/edit/
- **Методи**: GET, POST
- **Додаток**: worktypes
- **View-функція**: worktype_update
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_catalog_edit_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: admin (staff/superuser), director, admin (роль)
- **Опис**: Форма редагування виду роботи.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 18. Видалення виду роботи
- **URL**: /worktypes/<pk>/delete/
- **Методи**: GET, POST
- **Додаток**: worktypes
- **View-функція**: worktype_delete
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_catalog_edit_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: admin (staff/superuser), director, admin (роль)
- **Опис**: Сторінка підтвердження видалення виду роботи.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 19. Список постачальників
- **URL**: /suppliers/
- **Методи**: GET
- **Додаток**: suppliers
- **View-функція**: supplier_list
- **Декоратори**: @login_required
- **Перевірка ролі**: відсутня (читання), has_catalog_edit_permission() → can_edit в шаблоні
- **Multi-tenant**: Так — prepare_list_context()
- **Доступні ролі**: Усі аутентифіковані (читання); admin/director (редагування)
- **Опис**: Список постачальників з пагінацією.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 20. Створення постачальника
- **URL**: /suppliers/create/
- **Методи**: GET, POST
- **Додаток**: suppliers
- **View-функція**: supplier_create
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_catalog_edit_permission() → 403
- **Multi-tenant**: Так — форма обмежує компанію
- **Доступні ролі**: admin (staff/superuser), director, admin (роль)
- **Опис**: Форма створення постачальника.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 21. Редагування постачальника
- **URL**: /suppliers/<pk>/edit/
- **Методи**: GET, POST
- **Додаток**: suppliers
- **View-функція**: supplier_update
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_catalog_edit_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: admin (staff/superuser), director, admin (роль)
- **Опис**: Форма редагування постачальника.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 22. Видалення постачальника
- **URL**: /suppliers/<pk>/delete/
- **Методи**: GET, POST
- **Додаток**: suppliers
- **View-функція**: supplier_delete
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_catalog_edit_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: admin (staff/superuser), director, admin (роль)
- **Опис**: Сторінка підтвердження видалення постачальника.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 23. Список запчастин
- **URL**: /parts/
- **Методи**: GET
- **Додаток**: parts
- **View-функція**: part_list
- **Декоратори**: @login_required
- **Перевірка ролі**: відсутня (читання), has_catalog_edit_permission() та has_price_edit_permission() в шаблоні
- **Multi-tenant**: Так — prepare_list_context()
- **Доступні ролі**: Усі аутентифіковані (читання); admin/director (редагування); manager/purchaser (редагування ціни)
- **Опис**: Список запчастин з пагінацією.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 24. Створення запчастини
- **URL**: /parts/create/
- **Методи**: GET, POST
- **Додаток**: parts
- **View-функція**: part_create
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_catalog_edit_permission() → 403
- **Multi-tenant**: Так — форма обмежує компанію
- **Доступні ролі**: admin (staff/superuser), director, admin (роль)
- **Опис**: Форма створення запчастини. Враховано can_edit_price для форми.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 25. Редагування запчастини
- **URL**: /parts/<pk>/edit/
- **Методи**: GET, POST
- **Додаток**: parts
- **View-функція**: part_update
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_catalog_edit_permission() **АБО** has_price_edit_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: admin (staff/superuser), director, admin (роль) — повний доступ; manager, purchaser — тільки ціна
- **Опис**: Розумна форма редагування: якщо є purchase_orders — блокує ідентифікаційні поля. Якщо користувач має лише has_price_edit_permission — блокує всі поля крім selling_price.
- **Ризики**: Немає — добре продумана рольова логіка
- **Рекомендації**: Немає

---

### 26. Видалення запчастини
- **URL**: /parts/<pk>/delete/
- **Методи**: GET, POST
- **Додаток**: parts
- **View-функція**: part_delete
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_catalog_edit_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: admin (staff/superuser), director, admin (роль)
- **Опис**: Сторінка підтвердження видалення. Якщо є purchase_orders — 409 Conflict.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 27. Список закупівель
- **URL**: /purchases/
- **Методи**: GET
- **Додаток**: purchases
- **View-функція**: purchase_list
- **Декоратори**: @login_required
- **Перевірка ролі**: has_purchase_permission() → 403
- **Multi-tenant**: Так — prepare_list_context()
- **Доступні ролі**: admin (staff/superuser), director, admin, manager, purchaser, storekeeper
- **Опис**: Список замовлень закупівлі з пагінацією та can_edit для шаблону.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 28. Створення закупівлі
- **URL**: /purchases/create/
- **Методи**: GET, POST
- **Додаток**: purchases
- **View-функція**: purchase_create
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_purchase_edit_permission() → 403
- **Multi-tenant**: Так — поле company блокується для не-admin
- **Доступні ролі**: admin (staff/superuser), director, admin, manager, purchaser
- **Опис**: Форма створення замовлення закупівлі з inline formset для позицій.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 29. Деталі закупівлі
- **URL**: /purchases/<pk>/
- **Методи**: GET
- **Додаток**: purchases
- **View-функція**: purchase_detail
- **Декоратори**: @login_required
- **Перевірка ролі**: has_purchase_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: admin (staff/superuser), director, admin, manager, purchaser, storekeeper
- **Опис**: Детальна сторінка замовлення з усіма позиціями.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 30. Редагування закупівлі
- **URL**: /purchases/<pk>/edit/
- **Методи**: GET, POST
- **Додаток**: purchases
- **View-функція**: purchase_update
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_purchase_edit_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Захист від race conditions**: select_for_update(nowait=True) на POST
- **Доступні ролі**: admin (staff/superuser), director, admin, manager, purchaser
- **Опис**: Форма редагування замовлення (тільки DRAFT). Блокування рядка через select_for_update.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 31. Відправлення закупівлі
- **URL**: /purchases/<pk>/submit/
- **Методи**: **POST тільки** (@require_POST)
- **Додаток**: purchases
- **View-функція**: purchase_submit
- **Декоратори**: @login_required, @transaction.atomic, @require_POST
- **Перевірка ролі**: has_purchase_edit_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Захист**: select_for_update(nowait=True), перевірка статусу та наявності позицій
- **Доступні ролі**: admin (staff/superuser), director, admin, manager, purchaser
- **Опис**: Переводить замовлення з DRAFT у ORDERED. @require_POST запобігає випадковому відправленню через GET.
- **Ризики**: Немає — добре захищено
- **Рекомендації**: Немає

---

### 32. Оприбуткування закупівлі
- **URL**: /purchases/<pk>/receive/
- **Методи**: GET, POST
- **Додаток**: purchases
- **View-функція**: purchase_receive
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_purchase_permission() → 403 (тобто storekeeper також може)
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Захист**: select_for_update(nowait=True) на POST з перевіркою актуальності даних; F() вирази для атомарного оновлення залишків
- **Доступні ролі**: admin (staff/superuser), director, admin, manager, purchaser, storekeeper
- **Опис**: Форма оприбуткування товару. Оновлює складські залишки через PurchaseOrderService.receive_items().
- **Ризики**: Немає — найкращий захист серед усіх view
- **Рекомендації**: Немає

---

### 33. Скасування закупівлі
- **URL**: /purchases/<pk>/cancel/
- **Методи**: GET (підтвердження), POST (виконання)
- **Додаток**: purchases
- **View-функція**: purchase_cancel
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_purchase_edit_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Захист**: select_for_update(nowait=True) на POST; перевірка статусу
- **Доступні ролі**: admin (staff/superuser), director, admin, manager, purchaser
- **Опис**: Скасування замовлення (тільки DRAFT або ORDERED, не RECEIVED/CANCELLED).
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 34. Видалення закупівлі
- **URL**: /purchases/<pk>/delete/
- **Методи**: GET (підтвердження), POST (виконання)
- **Додаток**: purchases
- **View-функція**: purchase_delete
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_purchase_edit_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Захист**: select_for_update(nowait=True) на POST; перевірка is_editable
- **Доступні ролі**: admin (staff/superuser), director, admin, manager, purchaser
- **Опис**: Видалення замовлення (тільки DRAFT).
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 35. Список нарядів ⚠️ [P3-Low]
- **URL**: /workorders/
- **Методи**: GET
- **Додаток**: workorders
- **View-функція**: workorder_list
- **Декоратори**: @login_required
- **Перевірка ролі**: **ВІДСУТНЯ** (читання) — has_workorder_permission() передається в шаблон як can_edit
- **Multi-tenant**: Так — prepare_list_context()
- **Доступні ролі**: **Усі аутентифіковані**
- **Опис**: Список заказ-нарядів з пагінацією. Кнопки редагування/видалення приховані в UI для не-authorised ролей.
- **Ризики**: 🟢 **Низький** — дані захищені multi-tenant, але чутливі фінансові дані (вартість робіт, запчастин) доступні для прочитання всім співробітникам, включаючи бухгалтерів та закупівельників.
- **Рекомендації**:
  - Розглянути доцільність: майстри (mechanic) можуть потребувати перегляд нарядів для роботи. Поточна поведінка може бути свідомим бізнес-рішенням.

---

### 36. Деталі наряду ⚠️ [P3-Low]
- **URL**: /workorders/<pk>/
- **Методи**: GET
- **Додаток**: workorders
- **View-функція**: workorder_detail
- **Декоратори**: @login_required
- **Перевірка ролі**: **ВІДСУТНЯ** (читання) — has_workorder_permission() → can_edit в шаблоні
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: **Усі аутентифіковані**
- **Опис**: Детальна сторінка наряду з рядками робіт та запчастин, загальною вартістю.
- **Ризики**: 🟢 **Низький** — аналогічно списку, всі бачать фінансові деталі
- **Рекомендації**: Немає (якщо це свідоме бізнес-рішення)

---

### 37. Створення наряду
- **URL**: /workorders/create/
- **Методи**: GET, POST
- **Додаток**: workorders
- **View-функція**: workorder_create
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_workorder_permission() → 403
- **Multi-tenant**: Так — компанія встановлюється автоматично з поточного користувача
- **Доступні ролі**: admin (staff/superuser), director, admin (роль), manager
- **Опис**: Форма створення наряду з двома inline formsets (роботи та запчастини).
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 38. Редагування наряду
- **URL**: /workorders/<pk>/edit/
- **Методи**: GET, POST
- **Додаток**: workorders
- **View-функція**: workorder_update
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_workorder_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Доступні ролі**: admin (staff/superuser), director, admin (роль), manager
- **Опис**: Форма редагування наряду (тільки не-термінальні статуси). Оновлює складські залишки при зміні запчастин.
- **Ризики**: Немає
- **Рекомендації**: Немає

---

### 39. Видалення наряду
- **URL**: /workorders/<pk>/delete/
- **Методи**: GET, POST
- **Додаток**: workorders
- **View-функція**: workorder_delete
- **Декоратори**: @login_required, @transaction.atomic
- **Перевірка ролі**: has_workorder_permission() → 403
- **Multi-tenant**: Так — ilter_queryset_by_company() → 404
- **Захист**: select_for_update() з prefetch_related; F() вирази для повернення запчастин на склад
- **Доступні ролі**: admin (staff/superuser), director, admin (роль), manager
- **Опис**: Видалення наряду з автоматичним поверненням запчастин на склад (лише не-термінальні статуси).
- **Ризики**: Немає
- **Рекомендації**: Немає

---

## Загальні вразливості та рекомендації

### P1-High (критичні)

| # | Вразливість | Сторінки | Опис | Рекомендація |
|---|-------------|----------|------|--------------|
| P1-01 | **SECRET_KEY у коді** | — | У режимі DEBUG SECRET_KEY має fallback на 'dev-only-insecure-key-do-not-use-in-production' | Використовувати .env файл та валідацію. Поточне рішення прийнятне для dev, але критичне в prod. |
| P1-02 | **Відсутність рольової перевірки Vehicles CRUD** | vehicle_create, vehicle_update, vehicle_delete | Будь-який аутентифікований користувач може створювати/редагувати/видаляти автомобілі без обмежень за роллю. | Додати has_catalog_edit_permission() або is_admin_user() перевірку для цих view. |

### P2-Medium (високі)

| # | Вразливість | Сторінки | Опис | Рекомендація |
|---|-------------|----------|------|--------------|
| P2-01 | **Company update без multi-tenant фільтрації** | company_update | get_object_or_404(Company, pk=pk) не використовує ilter_queryset_by_company(). | Додати фільтрацію за компанією для консистентності. |
| P2-02 | **Company create/update використовує redirect замість 403** | company_create, company_update | При відсутності прав доступу виконується edirect('company_list') замість aise PermissionDenied(). | Використовувати однакову поведінку з іншими views — aise PermissionDenied(). |
| P2-03 | **Відсутність rate limiting у режимі DEBUG** | login | django-axes активний лише в 
ot DEBUG. | Розглянути додавання базового throttling навіть у dev-режимі. |
| P2-04 | **Employee delete каскадно видаляє User** | employee_delete | При видаленні Employee через OneToOneField(on_delete=CASCADE) видаляється і User. | Розглянути деактивацію замість видалення або зміну on_delete на SET_NULL. |

### P3-Low (низькі)

| # | Вразливість | Сторінки | Опис | Рекомендація |
|---|-------------|----------|------|--------------|
| P3-01 | **WorkOrder list/detail без перевірки ролі** | workorder_list, workorder_detail | Фінансові дані нарядів доступні всім аутентифікованим користувачам. | Якщо потрібно обмежити — додати has_workorder_permission(). |
| P3-02 | **Index page відсутність @login_required** | index | Анонімні користувачі бачать дашборд без даних (порожній). | Косметичне — не впливає на безпеку. |
| P3-03 | **Логування паролів** | employee_create | При створенні співробітника пароль передається через POST, але не логується. Перевірити, що logging не фіксує POST-дані. | Налаштувати middleware для фільтрації чутливих полів з логів. |

---

## Підсумок

**Загальна оцінка: Задовільний рівень безпеки**

Проєкт демонструє глибоке розуміння принципів безпеки:
- ✅ Multi-tenant ізоляція через ilter_queryset_by_company() у всіх критичних місцях
- ✅ Рольова модель з гнучкими перевірками (has_catalog_edit_permission, has_purchase_permission, has_workorder_permission)
- ✅ Захист від race conditions через select_for_update() та F() вирази
- ✅ Безпечна конфігурація: HSTS, CSP, Secure cookies, X-Frame-Options
- ✅ Захист від brute-force через django-axes (у продакшені)
- ✅ Атомарні транзакції для всіх write-операцій
- ✅ Логування подій безпеки (зміни статусів закупівель, видалення)

**Основні недоліки:**
1. **Відсутність рольової перевірки в Vehicles CRUD** (P1-02) — найсуттєвіша проблема
2. **Company update без multi-tenant фільтрації** (P2-01)
3. **Неконсистентна поведінка при відмові в доступі** (P2-02)

**Рекомендований план виправлення:**
1. Додати has_catalog_edit_permission() до ehicle_create, ehicle_update, ehicle_delete
2. Додати ilter_queryset_by_company() до company_update
3. Замінити edirect на aise PermissionDenied() у company_create та company_update
4. Розглянути обмеження доступу до перегляду нарядів (WorkOrder list/detail) для ролей, які не працюють з нарядами
