"""Тести представлень (views) додатку vehicles з перевіркою прав доступу."""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from company.models import Company
from vehicles.models import Vehicle


# ======================================================================
#  Vehicle LIST — доступний усім аутентифікованим
# ======================================================================


class TestVehicleListView:
    """Тести для vehicle_list view."""

    def test_anonymous_sees_empty_list(
        self,
        client: Client,
        vehicle: Vehicle,
    ) -> None:
        """Анонім перенаправляється на сторінку входу."""
        url: str = reverse("vehicle_list")
        response = client.get(url)
        assert response.status_code == 302

    def test_regular_user_sees_only_own_company(
        self,
        regular_client: Client,
        vehicle: Vehicle,
        other_company: Company,
    ) -> None:
        """Звичайний користувач бачить тільки автомобілі своєї компанії."""
        Vehicle.objects.create(
            vin_code="OTHERCOMPANYVIN000",
            brand="Audi",
            model="A4",
            year=2021,
            company=other_company,
        )
        url: str = reverse("vehicle_list")
        response = regular_client.get(url)
        vehicles_in_page: list = response.context["page_obj"]
        assert vehicle in vehicles_in_page
        assert len(vehicles_in_page) == 1

    def test_staff_user_sees_all_vehicles(
        self,
        staff_client: Client,
        vehicle: Vehicle,
        other_company: Company,
    ) -> None:
        """Staff бачить усі автомобілі з усіх компаній."""
        v2: Vehicle = Vehicle.objects.create(
            vin_code="STAFFSEESVIN00000",
            brand="Audi",
            model="Q7",
            year=2022,
            company=other_company,
        )
        url: str = reverse("vehicle_list")
        response = staff_client.get(url)
        vehicles_in_page: list = response.context["page_obj"]
        assert vehicle in vehicles_in_page
        assert v2 in vehicles_in_page


# ======================================================================
#  Vehicle QUICK-CREATE (JSON) — доступ лише admin/director/staff
# ======================================================================


class TestVehicleQuickCreateView:
    """Тести для vehicle_quick_create (JSON) view."""

    CREATE_DATA: dict = {
        "vin_code": "QUICKVIN000000017",
        "brand": "Toyota",
        "model": "Camry",
        "year": 2023,
        "engine_type": "hybrid",
        "engine_displacement": 2.5,
    }

    def test_anonymous_redirects(
        self,
        client: Client,
        db,
    ) -> None:
        """Анонім перенаправляється на вхід (302)."""
        url: str = reverse("vehicle_quick_create")
        response = client.get(url)
        assert response.status_code == 302

    def test_mechanic_gets_permission_denied(
        self,
        mechanic_client: Client,
    ) -> None:
        """Механік отримує 403 — створення лише для admin/director."""
        url: str = reverse("vehicle_quick_create")
        response = mechanic_client.get(url)
        assert response.status_code == 403

    def test_admin_can_create(
        self,
        admin_client: Client,
        admin_employee,
    ) -> None:
        """Адміністратор може створити авто через JSON."""
        url: str = reverse("vehicle_quick_create")
        response = admin_client.post(url, {**self.CREATE_DATA})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        created: Vehicle = Vehicle.objects.get(vin_code="QUICKVIN000000017")
        assert created.company == admin_employee.company
        assert created.brand == "Toyota"
        assert created.engine_type == Vehicle.EngineType.HYBRID

    def test_staff_can_create_in_any_company(
        self,
        staff_client: Client,
        other_company: Company,
    ) -> None:
        """Staff може створити авто в будь-якій компанії."""
        url: str = reverse("vehicle_quick_create")
        data: dict = {
            **self.CREATE_DATA,
            "vin_code": "STAFFQVIN00000001",
            "company": other_company.pk,
        }
        response = staff_client.post(url, data)
        assert response.status_code == 200
        data_json = response.json()
        assert data_json["success"] is True

        created: Vehicle = Vehicle.objects.get(vin_code="STAFFQVIN00000001")
        assert created.company == other_company

    def test_invalid_vin_returns_error(
        self,
        admin_client: Client,
    ) -> None:
        """VIN коротший за 17 символів — помилка валідації."""
        url: str = reverse("vehicle_quick_create")
        data: dict = {
            **self.CREATE_DATA,
            "vin_code": "SHORT",
        }
        response = admin_client.post(url, data)
        assert response.status_code == 400
        data_json = response.json()
        assert data_json["success"] is False
        assert "vin_code" in data_json["errors"]

    def test_invalid_year_returns_error(
        self,
        admin_client: Client,
    ) -> None:
        """Рік менший за 1900 — помилка валідації."""
        url: str = reverse("vehicle_quick_create")
        data: dict = {
            **self.CREATE_DATA,
            "vin_code": "YEARERRQVIN012345",
            "year": 1800,
        }
        response = admin_client.post(url, data)
        assert response.status_code == 400
        data_json = response.json()
        assert data_json["success"] is False


# ======================================================================
#  Vehicle UPDATE — доступ лише admin/director/staff
# ======================================================================


class TestVehicleUpdateView:
    """Тести для vehicle_update view."""

    def test_mechanic_gets_permission_denied(
        self,
        mechanic_client: Client,
        vehicle: Vehicle,
    ) -> None:
        """Механік отримує 403 при спробі редагувати."""
        url: str = reverse("vehicle_update", kwargs={"pk": vehicle.pk})
        response = mechanic_client.get(url)
        assert response.status_code == 403

    def test_admin_user_can_update_own_company_vehicle(
        self,
        admin_client: Client,
        vehicle: Vehicle,
    ) -> None:
        """Адміністратор може редагувати авто своєї компанії."""
        url: str = reverse("vehicle_update", kwargs={"pk": vehicle.pk})
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_admin_user_cannot_update_other_company_vehicle(
        self,
        admin_client: Client,
        other_company: Company,
    ) -> None:
        """Адміністратор не може редагувати авто чужої компанії (404)."""
        other_vehicle: Vehicle = Vehicle.objects.create(
            vin_code="OTHERCARVIN000000",
            brand="Ford",
            model="Focus",
            year=2020,
            company=other_company,
        )
        url: str = reverse("vehicle_update", kwargs={"pk": other_vehicle.pk})
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_update_vehicle_success(
        self,
        admin_client: Client,
        vehicle: Vehicle,
    ) -> None:
        """Успішне оновлення автомобіля."""
        url: str = reverse("vehicle_update", kwargs={"pk": vehicle.pk})
        response = admin_client.post(url, {
            "vin_code": vehicle.vin_code,
            "brand": "Mercedes",
            "model": "E-Class",
            "year": 2023,
            "engine_type": Vehicle.EngineType.DIESEL,
            "engine_displacement": 3.0,
            "company": vehicle.company.pk,
        })
        if response.status_code == 200 and response.context and response.context.get("form") and response.context["form"].errors:
            raise AssertionError(f"Form errors: {dict(response.context['form'].errors)}")
        vehicle.refresh_from_db()
        assert vehicle.brand == "Mercedes"
        assert vehicle.model == "E-Class"
        assert vehicle.year == 2023
        assert vehicle.engine_type == Vehicle.EngineType.DIESEL

    def test_update_vehicle_with_work_orders_disables_tech_fields(
        self,
        admin_client: Client,
        vehicle_with_work_order: Vehicle,
    ) -> None:
        """Редагування авто з нарядами — технічні поля недоступні (disabled).

        Нова поведінка: замість 409 показується форма з заблокованими
        технічними полями (vin_code, brand, model, year тощо).
        """
        url: str = reverse("vehicle_update", kwargs={"pk": vehicle_with_work_order.pk})
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.context['form'].fields['vin_code'].disabled is True
        assert response.context['form'].fields['brand'].disabled is True
        assert response.context['form'].fields['model'].disabled is True
        assert response.context['form'].fields['year'].disabled is True
        assert response.context['form'].fields['engine_type'].disabled is True
        assert response.context['form'].fields['engine_displacement'].disabled is True


# ======================================================================
#  Vehicle DELETE — доступ лише admin/director/staff
# ======================================================================


class TestVehicleDeleteView:
    """Тести для vehicle_delete view."""

    def test_mechanic_gets_permission_denied(
        self,
        mechanic_client: Client,
        vehicle: Vehicle,
    ) -> None:
        """Механік отримує 403 при спробі видалити."""
        url: str = reverse("vehicle_delete", kwargs={"pk": vehicle.pk})
        response = mechanic_client.post(url, follow=True)
        assert response.status_code == 403
        assert Vehicle.objects.filter(pk=vehicle.pk).exists()

    def test_admin_user_can_delete_own_company_vehicle(
        self,
        admin_client: Client,
        vehicle: Vehicle,
    ) -> None:
        """Адміністратор може видалити авто своєї компанії."""
        url: str = reverse("vehicle_delete", kwargs={"pk": vehicle.pk})
        response = admin_client.post(url, follow=True)
        assert not Vehicle.objects.filter(pk=vehicle.pk).exists()
        assert response.status_code == 200

    def test_admin_user_cannot_delete_other_company_vehicle(
        self,
        admin_client: Client,
        other_company: Company,
    ) -> None:
        """Адміністратор не може видалити чуже авто (404)."""
        other_vehicle: Vehicle = Vehicle.objects.create(
            vin_code="DELOTHERVIN000000",
            brand="Honda",
            model="Civic",
            year=2022,
            company=other_company,
        )
        url: str = reverse("vehicle_delete", kwargs={"pk": other_vehicle.pk})
        response = admin_client.post(url)
        assert response.status_code == 404
        assert Vehicle.objects.filter(pk=other_vehicle.pk).exists()

    def test_cannot_delete_vehicle_with_work_orders(
        self,
        admin_client: Client,
        vehicle_with_work_order: Vehicle,
    ) -> None:
        """Спроба видалити авто з нарядами — 409."""
        url: str = reverse("vehicle_delete", kwargs={"pk": vehicle_with_work_order.pk})
        response = admin_client.post(url, follow=True)
        assert response.status_code == 409
        assert Vehicle.objects.filter(pk=vehicle_with_work_order.pk).exists()
