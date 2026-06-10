"""Форми для додатку worktypes."""

from __future__ import annotations

from django import forms

from worktypes.models import WorkType


class WorkTypeForm(forms.ModelForm):
    """Форма створення та редагування виду роботи."""

    class Meta:
        model = WorkType
        fields = [
            'name', 'description', 'category', 'is_active', 'company',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Напр. Заміна масла',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Детальний опис роботи...',
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'company': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'Назва роботи',
            'description': 'Опис',
            'category': 'Категорія',
            'is_active': 'Активна',
            'company': 'Компанія',
        }
