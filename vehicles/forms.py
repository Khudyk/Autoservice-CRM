"""Форми для додатку vehicles."""

from __future__ import annotations

from django import forms

from vehicles.models import Vehicle


class VehicleForm(forms.ModelForm):
    """Форма створення та редагування автомобіля."""

    class Meta:
        model = Vehicle
        fields = [
            'vin_code', 'brand', 'model', 'year',
            'engine_type', 'engine_displacement', 'client', 'company',
        ]
        widgets = {
            'vin_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '17 символів VIN-коду',
            }),
            'brand': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Напр. Toyota',
            }),
            'model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Напр. Camry',
            }),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'engine_type': forms.Select(attrs={'class': 'form-control'}),
            'engine_displacement': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': '2.0',
            }),
            'client': forms.Select(attrs={'class': 'form-control'}),
            'company': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'vin_code': 'VIN-код',
            'brand': 'Марка',
            'model': 'Модель',
            'year': 'Рік випуску',
            'engine_type': 'Тип двигуна',
            'engine_displacement': "Об'єм двигуна, л",
            'client': 'Власник',
            'company': 'Компанія',
        }

    def clean_vin_code(self) -> str:
        """Валідація VIN-коду: нормалізація до верхнього регістру."""
        vin: str = self.cleaned_data.get('vin_code', '')
        if vin:
            vin = vin.upper().strip()
            if len(vin) != 17:
                raise forms.ValidationError(
                    'VIN-код має містити рівно 17 символів.',
                )
        return vin

    def clean_year(self) -> int:
        """Валідація року випуску: від 1900 до поточного + 1."""
        import datetime

        year: int = self.cleaned_data.get('year', 0)
        current_year: int = datetime.date.today().year
        if year < 1900 or year > current_year + 1:
            raise forms.ValidationError(
                f'Рік випуску має бути від 1900 до {current_year + 1}.',
            )
        return year
