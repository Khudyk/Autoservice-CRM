"""Форми для створення та редагування заказ-нарядів.

Містить:
- WorkOrderForm — основна форма наряду.
- WorkOrderServiceForm — форма рядка роботи.
- WorkOrderPartForm — форма рядка запчастини.
- WorkOrderServiceFormSet — набір форм для робіт.
- WorkOrderPartFormSet — набір форм для запчастин.
"""

from __future__ import annotations

from typing import Any

from django import forms
from django.db.models import F
from django.forms import inlineformset_factory

from accounts.models import Employee
from accounts.utils import is_admin_user as _is_admin_user
from clients.models import Client
from company.models import Company
from parts.models import Part, PartLot
from vehicles.models import Vehicle
from workorders.models import WorkOrder, WorkOrderService, WorkOrderPart
from worktypes.models import WorkType


class WorkOrderForm(forms.ModelForm):
    """Форма створення та редагування заказ-наряду.

    Поля `company` та `created_by` приховані — вони заповнюються
    автоматично з поточного користувача.
    """

    class Meta:
        model = WorkOrder
        fields = ('vehicle', 'client', 'mileage', 'status', 'notes')
        widgets = {
            'vehicle': forms.Select(attrs={'class': 'form-select'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'mileage': forms.NumberInput(attrs={
                'class': 'form-control', 'placeholder': 'напр. 125000',
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Ініціалізує форму з фільтрацією за компанією.

        Args:
            user: Об'єкт користувача (request.user) для ізоляції даних.
        """
        self._user: Any = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        user = self._user
        is_admin: bool = (
            user.is_authenticated and _is_admin_user(user=user)
            if user else False
        )
        company: Company | None = getattr(getattr(user, 'employee', None), 'company', None)

        # Автомобіль — фільтруємо за компанією користувача
        if is_admin:
            self.fields['vehicle'].queryset = Vehicle.objects.select_related('company').all()
        elif company:
            self.fields['vehicle'].queryset = Vehicle.objects.filter(company=company)
        else:
            self.fields['vehicle'].queryset = Vehicle.objects.none()

        # Поле "Клієнт" — всі клієнти без фільтра за компанією,
        # щоб можна було вибрати будь-кого, не тільки власника авто.
        # Автозаповнюється з vehicle.client через JS.
        self.fields['client'].queryset = Client.objects.select_related('company').all()
        self.fields['client'].required = False
        self.fields['client'].empty_label = '— Не вибрано —'
        # При редагуванні: підставляємо збереженого клієнта з наряду
        if self.instance.pk:
            self.fields['client'].initial = self.instance.client_id


class WorkOrderServiceForm(forms.ModelForm):
    """Форма рядка роботи/послуги в заказ-наряді."""

    class Meta:
        model = WorkOrderService
        fields = ('work_type', 'quantity', 'unit_price', 'employee', 'description')
        widgets = {
            'work_type': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Ініціалізує форму з фільтрацією виду робіт та виконавців.

        Args:
            user: Об'єкт користувача.
            company: Компанія для фільтрації (опціонально).
        """
        user: Any = kwargs.pop('user', None)
        company: Company | None = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

        is_admin: bool = (
            user.is_authenticated and _is_admin_user(user=user)
            if user else False
        )
        if not company and user and hasattr(user, 'employee'):
            company = getattr(user, 'employee').company

        # Фільтр видів робіт за компанією
        if is_admin:
            self.fields['work_type'].queryset = WorkType.objects.all()
        elif company:
            self.fields['work_type'].queryset = WorkType.objects.filter(company=company)
        else:
            self.fields['work_type'].queryset = WorkType.objects.none()

        # Фільтр виконавців: тільки співробітники з роллю 'mechanic' (Майстер)
        # Бізнес-правило: тільки майстри можуть виконувати роботи
        if is_admin:
            self.fields['employee'].queryset = (
                Employee.objects.select_related('user', 'company')
                .filter(roles__codename='mechanic')
            )
        elif company:
            self.fields['employee'].queryset = (
                Employee.objects.filter(company=company, roles__codename='mechanic')
            )
        else:
            self.fields['employee'].queryset = Employee.objects.none()


class WorkOrderPartForm(forms.ModelForm):
    """Форма рядка запчастини в заказ-наряді.

    Додано поле `part_lot` для вибору партії закупівлі.
    Дозволяє обрати лише партії з доступним залишком > 0.
    Валідує відповідність партії обраній запчастині
    та доступність кількості.
    """

    class Meta:
        model = WorkOrderPart
        fields = ('part', 'quantity', 'unit_price', 'part_lot')
        widgets = {
            'part': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'part_lot': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Ініціалізує форму з фільтрацією запчастин та партій за компанією.

        Args:
            user: Об'єкт користувача.
            company: Компанія для фільтрації (опціонально).
        """
        user: Any = kwargs.pop('user', None)
        company: Company | None = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

        is_admin: bool = (
            user.is_authenticated and _is_admin_user(user=user)
            if user else False
        )
        if not company and user and hasattr(user, 'employee'):
            company = getattr(user, 'employee').company

        # Фільтрація запчастин
        if is_admin:
            self.fields['part'].queryset = Part.objects.all()
        elif company:
            self.fields['part'].queryset = Part.objects.filter(company=company)
        else:
            self.fields['part'].queryset = Part.objects.none()

        # Фільтрація партій — тільки з доступним залишком > 0
        # quantity_available — property, тому фільтруємо через quantity > quantity_used
        if is_admin:
            lots_qs = PartLot.objects.select_related(
                'part', 'purchase_item__purchase_order',
            ).filter(quantity__gt=F('quantity_used'))
        elif company:
            lots_qs = PartLot.objects.select_related(
                'part', 'purchase_item__purchase_order',
            ).filter(company=company, quantity__gt=F('quantity_used'))
        else:
            lots_qs = PartLot.objects.none()

        self.fields['part_lot'].queryset = lots_qs
        self.fields['part_lot'].label = 'Партія закупівлі'
        self.fields['part_lot'].required = False
        self.fields['part_lot'].help_text = (
            'Виберіть партію для розрахунку прибутку. '
            'Показуються лише партії з доступним залишком.'
        )

    def clean(self) -> dict[str, Any]:
        """Валідує відповідність партії запчастині та доступність кількості.

        Returns:
            Очищені дані форми.

        Raises:
            forms.ValidationError: Якщо партія не відповідає запчастині
            або кількість перевищує доступний залишок у партії.
        """
        cleaned_data: dict[str, Any] = super().clean()
        part = cleaned_data.get('part')
        lot = cleaned_data.get('part_lot')
        quantity = cleaned_data.get('quantity')

        if lot and part and lot.part_id != part.pk:
            self.add_error(
                'part_lot',
                f'Партія "{lot}" не відповідає обраній запчастині "{part}".',
            )

        if lot and quantity is not None:
            available = lot.quantity_available
            if quantity > available:
                self.add_error(
                    'quantity',
                    f'У вибраній партії доступно лише {available} '
                    f'{lot.part.get_unit_display()}. '
                    f'Запитано {quantity}.',
                )

        return cleaned_data


# --- Набори форм (inline formsets) ---

WorkOrderServiceFormSet = inlineformset_factory(
    WorkOrder,
    WorkOrderService,
    form=WorkOrderServiceForm,
    extra=2,
    can_delete=True,
)

WorkOrderPartFormSet = inlineformset_factory(
    WorkOrder,
    WorkOrderPart,
    form=WorkOrderPartForm,
    extra=2,
    can_delete=True,
)
