"""Форми для додатку suppliers."""

from __future__ import annotations

from django import forms

from suppliers.models import Supplier


class SupplierForm(forms.ModelForm):
    """Форма створення та редагування постачальника."""

    class Meta:
        model = Supplier
        fields = [
            'name', 'contact_person', 'phone', 'email',
            'address', 'notes', 'is_active', 'company',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Напр. ТОВ "Автозапчастини"',
            }),
            'contact_person': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ПІБ контактної особи',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+380 XX XXX XX XX',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'info@example.com',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Фактична адреса',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Додаткова інформація...',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'company': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'Назва постачальника',
            'contact_person': 'Контактна особа',
            'phone': 'Телефон',
            'email': 'Email',
            'address': 'Адреса',
            'notes': 'Нотатки',
            'is_active': 'Активний',
            'company': 'Компанія',
        }
