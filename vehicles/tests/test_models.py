"""Тести моделі Vehicle."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from vehicles.models import Vehicle


class TestVehicleModel:
    """Тести для моделі Vehicle."""

    def test_vehicle_str_returns_brand_model_vin(
        self,
        vehicle: Vehicle,
    ) -> None:
        """Перевіряє, що __str__ повертає 'Марка Модель (VIN)'."""
        expected: str = f'{vehicle.brand} {vehicle.model} ({vehicle.vin_code})'
        assert str(vehicle) == expected

    def test_vin_code_unique_per_company(
        self,
        vehicle: Vehicle,
        company,
    ) -> None:
        """Перевіряє унікальність VIN в межах компанії."""
        with pytest.raises(IntegrityError):
            Vehicle.objects.create(
                vin_code='WBA3A5C5XDF123456',
                brand='BMW',
                model='X5',
                year=2021,
                engine_type=Vehicle.EngineType.DIESEL,
                engine_displacement=3.0,
                company=company,
            )

    def test_same_vin_different_company_allowed(
        self,
        vehicle: Vehicle,
        other_company,
    ) -> None:
        """Перевіряє, що однаковий VIN може бути в різних компаніях."""
        v2: Vehicle = Vehicle.objects.create(
            vin_code='WBA3A5C5XDF123456',
            brand='BMW',
            model='X5',
            year=2021,
            engine_type=Vehicle.EngineType.DIESEL,
            engine_displacement=3.0,
            company=other_company,
        )
        assert v2.pk is not None
        assert v2.vin_code == vehicle.vin_code
        assert v2.company != vehicle.company

    def test_engine_displacement_null_for_electric(
        self,
        company,
    ) -> None:
        """Перевіряє, що для електромобіля об'єм двигуна може бути null."""
        ev: Vehicle = Vehicle.objects.create(
            vin_code='ELECTRICVIN00001',
            brand='Tesla',
            model='Model 3',
            year=2023,
            engine_type=Vehicle.EngineType.ELECTRIC,
            engine_displacement=None,
            company=company,
        )
        assert ev.engine_displacement is None

    def test_vehicle_creation_sets_timestamps(
        self,
        vehicle: Vehicle,
    ) -> None:
        """Перевіряє, що created_at та updated_at заповнюються автоматично."""
        assert vehicle.created_at is not None
        assert vehicle.updated_at is not None

    def test_default_engine_type_is_petrol(
        self,
        company,
    ) -> None:
        """Перевіряє, що тип двигуна за замовчуванням — Бензин."""
        v: Vehicle = Vehicle.objects.create(
            vin_code='DEFAULTENGINE001',
            brand='Toyota',
            model='Camry',
            year=2022,
            company=company,
        )
        assert v.engine_type == Vehicle.EngineType.PETROL
