"""Форми для модуля співробітників."""

from __future__ import annotations

from typing import Any

from django import forms
from django.contrib.auth.models import User

from accounts.models import Employee, Role
from accounts.utils import get_user_company, is_admin_user
from company.models import Company


class EmployeeForm(forms.ModelForm):
    """Форма створення та редагування співробітника.

    При створенні — дозволяє ввести дані нового користувача (username,
    email, password, first_name, last_name) та створити User + Employee
    одним запитом.

    При редагуванні — показує дані користувача (крім пароля).
    """

    # --- Поля для користувача (User) ---
    username = forms.CharField(
        label="Ім'я користувача",
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=False,
        help_text='Тільки для нового співробітника',
    )
    email = forms.EmailField(
        label='Email',
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )
    first_name = forms.CharField(
        label="Ім'я",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    last_name = forms.CharField(
        label='Прізвище',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    password = forms.CharField(
        label='Пароль',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='Залиште порожнім, щоб не змінювати',
    )

    # --- Поле компанії ---
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(),
        label='Компанія',
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
    )

    class Meta:
        model = Employee
        fields = ['company', 'roles', 'phone', 'is_active', 'parts_sale_percent', 'labor_percent']
        widgets = {
            'roles': forms.CheckboxSelectMultiple(attrs={'class': 'role-chip-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'parts_sale_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100',
            }),
            'labor_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100',
            }),
        }
        labels = {
            'roles': 'Ролі',
            'phone': 'Телефон',
            'is_active': 'Активний',
            'parts_sale_percent': 'Відсоток від продажу запчастин',
            'labor_percent': 'Відсоток від робіт',
        }
        help_texts = {
            'parts_sale_percent': 'Від 0% до 100%',
            'labor_percent': 'Від 0% до 100%',
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Ініціалізує форму залежно від режиму (create/update) та прав.

        Args:
            user: Django User, для якого налаштовується форма.
        """
        current_user: User | None = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        is_update: bool = self.instance.pk is not None

        # Налаштування компанії
        if current_user and current_user.is_authenticated:
            if not is_admin_user(request=None, user=current_user):
                company: Company | None = get_user_company(
                    request=None, user=current_user,
                )
                if company:
                    self.fields['company'].queryset = Company.objects.filter(
                        pk=company.pk,
                    )
                    self.fields['company'].initial = company
                    self.fields['company'].disabled = True
                else:
                    self.fields['company'].queryset = Company.objects.none()

        # Режим редагування — підставляємо дані користувача
        if is_update and self.instance.user_id:
            user: User = self.instance.user
            self.fields['username'].initial = user.username
            self.fields['username'].disabled = True
            self.fields['username'].help_text = ''
            self.fields['email'].initial = user.email
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['password'].required = False
            self.fields['password'].help_text = 'Залиште порожнім, щоб не змінювати'
        else:
            # Режим створення — username обов'язковий
            self.fields['username'].required = True
            self.fields['username'].help_text = ''

    def clean_username(self) -> str:
        """Перевіряє унікальність username при створенні."""
        username: str = self.cleaned_data.get('username', '')
        if not username:
            return username
        if self.instance.pk is None and User.objects.filter(
            username=username,
        ).exists():
            raise forms.ValidationError(
                f"Користувач з ім'ям «{username}» вже існує.",
            )
        return username

    def save(self, commit: bool = True) -> Employee:
        """Створює/оновлює User та Employee в одному методі.

        Returns:
            Employee (створений або оновлений).
        """
        employee: Employee = super().save(commit=False)

        # Отримуємо або створюємо користувача
        username: str = self.cleaned_data.get('username', '')
        email: str = self.cleaned_data.get('email', '')
        first_name: str = self.cleaned_data.get('first_name', '')
        last_name: str = self.cleaned_data.get('last_name', '')
        password: str = self.cleaned_data.get('password', '')

        if self.instance.pk is None:
            # Створення нового користувача
            user: User = User.objects.create_user(
                username=username,
                email=email,
                password=password or User.objects.make_random_password(),
                first_name=first_name,
                last_name=last_name,
            )
            employee.user = user
        else:
            # Оновлення існуючого користувача
            user: User = employee.user
            if email:
                user.email = email
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            if password:
                user.set_password(password)
            user.save()

        if commit:
            employee.save()
            # Зберігаємо M2M зв'язки (ролі), які були відкладені через commit=False
            self.save_m2m()

        return employee
