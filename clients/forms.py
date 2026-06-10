"""Форми для додатку clients."""

from __future__ import annotations

import re

from django import forms
from django.core.exceptions import ValidationError

from clients.models import Client


class ClientForm(forms.ModelForm):
    """Форма створення/редагування клієнта."""

    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'phone', 'email', 'notes', 'company']
        widgets = {
            'first_name': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': "Ім'я або назва організації"},
            ),
            'last_name': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Прізвище (для ФОП — залиште порожнім)'},
            ),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'inputmode': 'numeric',
                'pattern': '[0-9]*',
                'placeholder': '380501234567',
                'maxlength': '12',
                'data-phone-input': 'true',
            }),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'company': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'first_name': "Ім'я / Назва",
            'last_name': 'Прізвище',
        }

    def clean_phone(self) -> str:
        """Очищує телефон: лише цифри, формат 380XXXXXXXXX.

        Алгоритм нормалізації:
        1. Видаляє всі символи, крім цифр.
        2. Якщо номер починається з '8' — відкидає '8' (старий
           міжміський префікс).
        3. Якщо після цього починається з '0' — відкидає '0'
           (внутрішній префікс України).
        4. Додає код країни '380', якщо його ще немає.
        5. Фінальний формат: 380 + 9 цифр = 12 цифр.

        Returns:
            Очищений номер телефону (лише цифри).
        """
        phone: str = self.cleaned_data.get('phone', '')
        if not phone:
            raise ValidationError('Номер телефону обов\'язковий.')

        # Видаляємо всі нецифрові символи
        digits_only: str = re.sub(r'\D', '', phone)

        if not digits_only:
            raise ValidationError('Номер телефону має містити хоча б одну цифру.')

        # Нормалізація до формату 380XXXXXXXXX
        # Крок 1: відкидаємо старий міжміський префікс '8'
        if digits_only.startswith('8'):
            digits_only = digits_only[1:]

        # Крок 2: відкидаємо внутрішній префікс '0'
        if digits_only.startswith('0'):
            digits_only = digits_only[1:]

        # Крок 3: додаємо код країни, якщо ще не має
        if not digits_only.startswith('380'):
            digits_only = '380' + digits_only

        # Крок 4: обрізаємо до 12 цифр (на випадок, якщо ввели зайве)
        normalized: str = digits_only[:12]

        # Перевірка довжини
        if len(normalized) != 12:
            raise ValidationError(
                'Номер телефону має містити 12 цифр у форматі 380XXXXXXXXX '
                f'(отримано {len(normalized)} цифр).'
            )

        return normalized
