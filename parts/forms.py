"""Форми для додатку parts."""

from __future__ import annotations

from typing import Any

from django import forms

from parts.models import Part


class PartForm(forms.ModelForm):
    """Форма створення та редагування запчастини.

    Підтримує динамічне блокування полів:
    - `disable_identity_fields=True` — блокує поля назви, артикула, виробника
      та одиниці виміру (при наявності прихідних накладних, щоб не порушити
      цілісність довідника)
    - `can_edit_price=False` — блокує поле продажної ціни (для користувачів
      без відповідних прав)
    """

    def __init__(
        self,
        *args: Any,
        disable_identity_fields: bool = False,
        can_edit_price: bool = True,
        **kwargs: Any,
    ) -> None:
        """Ініціалізує форму з можливістю блокування полів.

        Args:
            disable_identity_fields: Якщо True, поля name, part_number,
                manufacturer та unit стають недоступними для редагування
                (при наявності прихідних накладних).
            can_edit_price: Якщо False, поле selling_price стає недоступним
                для редагування (для користувачів без прав на ціни).
        """
        super().__init__(*args, **kwargs)

        if disable_identity_fields:
            self.fields['name'].disabled = True
            self.fields['part_number'].disabled = True
            self.fields['manufacturer'].disabled = True
            self.fields['unit'].disabled = True

        if not can_edit_price:
            self.fields['selling_price'].disabled = True

    class Meta:
        model = Part
        fields = [
            'name', 'part_number', 'manufacturer', 'unit',
            'selling_price',
            'min_quantity', 'location',
            'is_active', 'company',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Напр. Масляний фільтр',
            }),
            'part_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Напр. OC 260',
            }),
            'manufacturer': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Напр. MANN-FILTER',
            }),
            'unit': forms.Select(attrs={'class': 'form-control'}),
            'selling_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'min_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Напр. Стелаж A, полиця 3',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'company': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'Назва запчастини',
            'part_number': 'Артикул',
            'manufacturer': 'Виробник',
            'unit': 'Одиниця виміру',
            'selling_price': 'Ціна продажу, грн',
            'min_quantity': 'Мінімальний залишок',
            'location': 'Місце на складі',
            'is_active': 'Активна',
            'company': 'Компанія',
        }
