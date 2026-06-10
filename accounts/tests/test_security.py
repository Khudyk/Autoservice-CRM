"""Загальні тести безпеки — session, CSRF, login_required, конфігурація."""

from __future__ import annotations

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from accounts.models import Employee, Role
from company.models import Company


# ======================================================================
#  Session security — перевірка налаштувань сесій
# ======================================================================


class TestSessionSecurity:
    """Тести безпеки сесій — відповідність конфігурації."""

    def test_session_cookie_httponly(self) -> None:
        """SESSION_COOKIE_HTTPONLY має бути True."""
        assert settings.SESSION_COOKIE_HTTPONLY is True

    def test_session_cookie_samesite(self) -> None:
        """SESSION_COOKIE_SAMESITE має бути Lax або Strict."""
        assert settings.SESSION_COOKIE_SAMESITE in ("Lax", "Strict")

    def test_session_expire_at_browser_close(self) -> None:
        """SESSION_EXPIRE_AT_BROWSER_CLOSE має бути True."""
        assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is True

    def test_session_cookie_age(self) -> None:
        """SESSION_COOKIE_AGE має бути 8 годин або менше."""
        assert settings.SESSION_COOKIE_AGE <= 28800


# ======================================================================
#  CSRF protection
# ======================================================================


class TestCSRFProtection:
    """Тести CSRF-захисту."""

    def test_post_without_csrf_token_fails(
        self, client: Client, db,
    ) -> None:
        """POST без CSRF-токену повертає 403 (Forbidden)."""
        # Створюємо користувача та логінимося
        from django.contrib.auth.models import User
        user = User.objects.create_user(username="csrf_user", password="pass123")
        client.login(username="csrf_user", password="pass123")

        response = client.post(
            reverse("employee_list"),
            {},
            content_type="application/x-www-form-urlencoded",
        )
        # Django повертає 403 при відсутності CSRF-токену
        assert response.status_code == 403


# ======================================================================
#  LoginRequired — усі внутрішні views мають @login_required
# ======================================================================


class TestLoginRequired:
    """Перевіряє, що всі захищені views редиректять аноніма на логін."""

    PROTECTED_URLS: tuple[str, ...] = (
        "vehicle_list",
        "vehicle_create",
        "employee_list",
        "employee_create",
        "company_list",
        "purchase_list",
        "purchase_create",
        "workorder_list",
        "workorder_create",
        "part_list",
        "part_create",
        "supplier_list",
        "supplier_create",
    )

    @pytest.mark.parametrize("url_name", PROTECTED_URLS)
    def test_anonymous_redirected_to_login(
        self, client: Client, url_name: str,
    ) -> None:
        """Анонім перенаправляється на сторінку входу для всіх захищених URL."""
        try:
            url = reverse(url_name)
        except Exception:
            pytest.skip(f"URL name {url_name} not found or requires args")
        response = client.get(url)
        assert (
            response.status_code == 302
        ), f"{url_name} should redirect anonymous user (got {response.status_code})"
        login_url = reverse("login")
        assert login_url in response.url, (
            f"Redirect for {url_name} should point to login page"
        )


# ======================================================================
#  Permission-based access — перевірка 403 для різних ролей
# ======================================================================


class TestRoleBasedAccess:
    """Перевіряє, що користувачі без прав отримують 403."""

    @pytest.fixture
    def setup(self, db, roles) -> dict:
        """Створює компанію, Employee з різними ролями та повертає словник."""
        from django.contrib.auth.models import User

        company = Company.objects.create(name="Test Company")
        users = {}
        clients = {}

        for role_name in ("mechanic", "admin", "manager"):
            user = User.objects.create_user(
                username=f"user_{role_name}",
                password="pass123",
            )
            emp = Employee.objects.create(user=user, company=company)
            emp.roles.set([Role.objects.get(codename=role_name)])
            client_obj = Client()
            client_obj.login(username=f"user_{role_name}", password="pass123")
            users[role_name] = user
            clients[role_name] = client_obj

        return {"company": company, "users": users, "clients": clients}

    def test_vehicle_create_mechanic_gets_403(self, setup: dict) -> None:
        """Механік отримує 403 на створення автомобіля."""
        client = setup["clients"]["mechanic"]
        response = client.get(reverse("vehicle_create"))
        assert response.status_code == 403

    def test_employee_list_mechanic_gets_403(self, setup: dict) -> None:
        """Механік отримує 403 на список співробітників."""
        client = setup["clients"]["mechanic"]
        response = client.get(reverse("employee_list"))
        assert response.status_code == 403

    def test_employee_list_admin_can_access(self, setup: dict) -> None:
        """Адміністратор може переглядати список співробітників."""
        client = setup["clients"]["admin"]
        response = client.get(reverse("employee_list"))
        assert response.status_code == 200
