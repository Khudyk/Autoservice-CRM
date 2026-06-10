"""Форми для керування компаніями.

Надає форму створення та редагування компанії з Bootstrap-стилізацією.
"""

from django import forms

from company.models import Company


class CompanyForm(forms.ModelForm):
    """Форма створення та редагування компанії (автосервісу).

    Використовується в представленнях `company_create` та `company_update`
    для введення реквізитів компанії: назви, контактних даних та нотаток.
    """

    class Meta:
        model = Company
        fields = ["name", "email", "phone", "address", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
