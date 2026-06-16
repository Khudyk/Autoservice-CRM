"""Форми для додатку purchases — закупівля запчастин."""

from __future__ import annotations

from decimal import Decimal

from django import forms

from parts.models import Part
from purchases.models import PurchaseOrder, PurchaseOrderItem, SupplierPayment
from suppliers.models import Supplier


class PurchaseOrderForm(forms.ModelForm):
    """Основна форма замовлення закупівлі."""

    def __init__(self, *args: Any, company: Any = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields['supplier'].queryset = Supplier.objects.filter(company=company)

    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'notes', 'company']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Нотатки до замовлення...',
            }),
            'company': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'supplier': 'Постачальник',
            'notes': 'Нотатки',
            'company': 'Компанія',
        }


class PurchaseOrderItemForm(forms.ModelForm):
    """Форма позиції замовлення для inline formset."""

    def __init__(self, *args: Any, company: Any = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields['part'].queryset = Part.objects.filter(company=company)

    class Meta:
        model = PurchaseOrderItem
        fields = ['part', 'quantity_ordered', 'unit_price']
        widgets = {
            'part': forms.Select(attrs={'class': 'form-control part-select'}),
            'quantity_ordered': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1',
                'min': '0.01',
                'placeholder': '1',
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
            }),
        }
        labels = {
            'part': 'Запчастина',
            'quantity_ordered': 'Кількість',
            'unit_price': 'Ціна, грн',
        }


PurchaseOrderItemFormSet = forms.inlineformset_factory(
    parent_model=PurchaseOrder,
    model=PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class PurchaseReceiveForm(forms.Form):
    """Форма для оприбуткування позицій замовлення.

    Динамічно створюється під кожну позицію, яка ще не отримана повністю.
    """

    def __init__(
        self,
        *args,
        items: list[PurchaseOrderItem] | None = None,
        **kwargs,
    ) -> None:
        """Ініціалізує форму з полями для кожної позиції.

        Args:
            items: Список позицій замовлення для отримання.
        """
        super().__init__(*args, **kwargs)
        self._items: list[PurchaseOrderItem] = items or []

        for item in self._items:
            remaining: Decimal = item.remaining_to_receive
            field_name: str = f'item_{item.pk}'
            self.fields[field_name] = forms.DecimalField(
                label=f'{item.part.name} (арт. {item.part.part_number or "—"})',
                initial=remaining,
                min_value=0,
                max_value=float(remaining),
                decimal_places=2,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control',
                    'step': '0.01',
                }),
                help_text=f'Замовлено: {item.quantity_ordered}, '
                          f'вже отримано: {item.quantity_received}, '
                          f'доступно: {remaining}',
            )

    def get_receive_data(self) -> list[tuple[PurchaseOrderItem, Decimal]]:
        """Повертає список (позиція, кількість_до_отримання)."""
        result: list[tuple[PurchaseOrderItem, Decimal]] = []
        for item in self._items:
            field_name: str = f'item_{item.pk}'
            qty: Decimal = Decimal(str(self.cleaned_data.get(field_name, 0)))
            if qty > 0:
                result.append((item, qty))
        return result


class SupplierPaymentForm(forms.ModelForm):
    """Форма створення та редагування платежу постачальнику.

    Номер платежу (payment_number) генерується автоматично
    в presentation-шарі (view) і не редагується вручну.
    Поле purchase_order фільтрується за вибраним постачальником
    (supplier_id передається з view) і показує номер + суму замовлення.
    """

    def __init__(
        self,
        *args,
        supplier_id: int | None = None,
        company: Any = None,
        **kwargs,
    ) -> None:
        """Ініціалізує форму з фільтрацією замовлень за постачальником.

        Args:
            supplier_id: ID постачальника для фільтрації списку замовлень.
            company: Компанія для фільтрації списків постачальників та замовлень.
        """
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields['supplier'].queryset = Supplier.objects.filter(
                company=company,
            )
            self.fields['purchase_order'].queryset = (
                self.fields['purchase_order'].queryset.filter(
                    company=company,
                )
            )
        if supplier_id:
            self.fields['purchase_order'].queryset = (
                self.fields['purchase_order'].queryset.filter(
                    supplier_id=supplier_id,
                )
            )
        # Показуємо номер + суму замовлення в випадаючому списку
        self.fields['purchase_order'].label_from_instance = (
            lambda obj: (
                f'{obj.order_number} — {obj.total_amount:,.2f} грн'
            )
        )

    class Meta:
        model = SupplierPayment
        fields = [
            'supplier', 'amount', 'payment_date', 'payment_type',
            'status', 'purchase_order', 'notes', 'company',
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00',
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'payment_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'purchase_order': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Призначення платежу, номер рахунку...',
            }),
            'company': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'supplier': 'Постачальник',
            'amount': 'Сума, грн',
            'payment_date': 'Дата оплати',
            'payment_type': 'Спосіб оплати',
            'status': 'Статус',
            'purchase_order': 'Замовлення (необов\'язково)',
            'notes': 'Нотатки',
            'company': 'Компанія',
        }
