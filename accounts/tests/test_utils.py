"""Тести мульти-тенантних утиліт з accounts/utils.py."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.http import Http404, HttpRequest
from django.test import RequestFactory

from accounts.models import Employee
from accounts.utils import (
    filter_queryset_by_company,
    get_object_or_404_for_company,
    get_user_company,
    is_admin_user,
    paginate_queryset,
)
from company.models import Company
from parts.models import Part


class TestGetUserCompany:
    """Тести для get_user_company."""

    def test_returns_company_for_employee(
        self,
        employee: Employee,
        company: Company,
    ) -> None:
        """Повертає компанію співробітника."""
        request = RequestFactory().get('/')
        request.user = employee.user
        result = get_user_company(request)
        assert result == company

    def test_returns_none_for_anonymous(self) -> None:
        """Анонімний користувач повертає None."""
        request = RequestFactory().get('/')
        request.user = type('AnonymousUser', (), {'is_authenticated': False})()
        result = get_user_company(request)
        assert result is None

    def test_returns_none_when_no_employee(self, db: None) -> None:
        """Користувач без Employee повертає None."""
        request = RequestFactory().get('/')
        request.user = User.objects.create_user(username='no_emp')
        result = get_user_company(request)
        assert result is None


class TestIsAdminUser:
    """Тести для is_admin_user."""

    def test_staff_is_admin(self, employee: Employee) -> None:
        """staff користувач повертає True."""
        employee.user.is_staff = True
        employee.user.save()
        request = RequestFactory().get('/')
        request.user = employee.user
        assert is_admin_user(request) is True

    def test_superuser_is_admin(self, employee: Employee) -> None:
        """superuser повертає True."""
        employee.user.is_superuser = True
        employee.user.save()
        request = RequestFactory().get('/')
        request.user = employee.user
        assert is_admin_user(request) is True

    def test_regular_user_is_not_admin(self, employee: Employee) -> None:
        """Звичайний користувач повертає False."""
        employee.user.is_staff = False
        employee.user.is_superuser = False
        employee.user.save()
        request = RequestFactory().get('/')
        request.user = employee.user
        assert is_admin_user(request) is False

    def test_anonymous_is_not_admin(self) -> None:
        """Анонім повертає False."""
        request = RequestFactory().get('/')
        request.user = type('AnonymousUser', (), {'is_authenticated': False})()
        assert is_admin_user(request) is False


class TestFilterQuerysetByCompany:
    """Тести для filter_queryset_by_company."""

    def test_filters_to_users_company(
        self,
        employee: Employee,
        company: Company,
    ) -> None:
        """Звичайний користувач бачить тільки свою компанію."""
        other_company = Company.objects.create(name='Інша компанія')
        # Створюємо запчастини в обох компаніях
        part_own = Part.objects.create(
            name='Моя деталь', company=company,
            part_number='OWN-001', selling_price=100,
        )
        Part.objects.create(
            name='Чужа деталь', company=other_company,
            part_number='OTHER-001', selling_price=200,
        )
        request = RequestFactory().get('/')
        request.user = employee.user
        qs = filter_queryset_by_company(request, Part.objects.all())
        assert part_own in qs
        assert qs.count() == 1

    def test_staff_sees_all(
        self,
        employee: Employee,
        company: Company,
    ) -> None:
        """Staff користувач бачить усі компанії."""
        employee.user.is_staff = True
        employee.user.save()
        other_company = Company.objects.create(name='Інша компанія')
        Part.objects.create(
            name='Чужа деталь', company=other_company,
            part_number='OTHER-001', selling_price=200,
        )
        request = RequestFactory().get('/')
        request.user = employee.user
        qs = filter_queryset_by_company(request, Part.objects.all())
        assert qs.count() == 1  # бачить чужу

    def test_returns_none_when_no_company(
        self,
        employee: Employee,
    ) -> None:
        """Користувач без прив'язки до компанії отримує пустий QS."""
        # Створюємо користувача без Employee
        user_no_company = User.objects.create_user(username='no_company')
        request = RequestFactory().get('/')
        request.user = user_no_company
        qs = filter_queryset_by_company(request, Part.objects.all())
        assert qs.count() == 0

    def test_custom_field_name(
        self,
        employee: Employee,
        company: Company,
    ) -> None:
        """Працює з кастомним ім'ям поля компанії."""
        other_company = Company.objects.create(name='Інша компанія')
        part_own = Part.objects.create(
            name='Моя деталь', company=company,
            part_number='OWN-001', selling_price=100,
        )
        request = RequestFactory().get('/')
        request.user = employee.user
        # Фільтруємо за стандартним полем 'company'
        qs = filter_queryset_by_company(request, Part.objects.all())
        assert part_own in qs


class TestGetObjectOr404ForCompany:
    """Тести для get_object_or_404_for_company."""

    def test_returns_object_for_own_company(
        self,
        employee: Employee,
        company: Company,
    ) -> None:
        """Повертає об'єкт своєї компанії."""
        part = Part.objects.create(
            name='Моя деталь', company=company,
            part_number='OWN-001', selling_price=100,
        )
        request = RequestFactory().get('/')
        request.user = employee.user
        result = get_object_or_404_for_company(request, Part, pk=part.pk)
        assert result == part

    def test_raises_404_for_other_company(
        self,
        employee: Employee,
        company: Company,
    ) -> None:
        """Піднімає Http404 для об'єкта іншої компанії."""
        other_company = Company.objects.create(name='Інша компанія')
        part = Part.objects.create(
            name='Чужа деталь', company=other_company,
            part_number='OTHER-001', selling_price=200,
        )
        request = RequestFactory().get('/')
        request.user = employee.user
        with pytest.raises(Http404):
            get_object_or_404_for_company(request, Part, pk=part.pk)

    def test_staff_can_access_any_company(
        self,
        employee: Employee,
        company: Company,
    ) -> None:
        """Staff може отримати об'єкт будь-якої компанії."""
        employee.user.is_staff = True
        employee.user.save()
        other_company = Company.objects.create(name='Інша компанія')
        part = Part.objects.create(
            name='Чужа деталь', company=other_company,
            part_number='OTHER-001', selling_price=200,
        )
        request = RequestFactory().get('/')
        request.user = employee.user
        result = get_object_or_404_for_company(request, Part, pk=part.pk)
        assert result == part

    def test_works_with_queryset(
        self,
        employee: Employee,
        company: Company,
    ) -> None:
        """Працює коли передано QuerySet замість класу моделі."""
        part = Part.objects.create(
            name='Моя деталь', company=company,
            part_number='OWN-001', selling_price=100,
        )
        request = RequestFactory().get('/')
        request.user = employee.user
        result = get_object_or_404_for_company(
            request,
            Part.objects.select_related('company'),
            pk=part.pk,
        )
        assert result == part

    def test_raises_404_for_nonexistent(
        self,
        employee: Employee,
        company: Company,
    ) -> None:
        """Піднімає Http404 для неіснуючого об'єкта."""
        request = RequestFactory().get('/')
        request.user = employee.user
        with pytest.raises(Http404):
            get_object_or_404_for_company(request, Part, pk=99999)


class TestPaginateQueryset:
    """Тести для paginate_queryset."""

    def test_returns_page(self, employee: Employee) -> None:
        """Повертає об'єкт Page."""
        request = RequestFactory().get('/')
        request.user = employee.user
        qs = Part.objects.none()
        page = paginate_queryset(request, qs)
        assert page is not None

    def test_paginates_correctly(self, employee: Employee) -> None:
        """Правильно розбиває на сторінки."""
        request = RequestFactory().get('/?page=1')
        request.user = employee.user
        # Створюємо 5 об'єктів
        company = employee.company
        parts = []
        for i in range(5):
            p = Part.objects.create(
                name=f'Деталь {i}', company=company,
                part_number=f'P-{i:03d}', selling_price=100,
            )
            parts.append(p)
        page = paginate_queryset(request, Part.objects.all(), per_page=2)
        assert page.has_other_pages() is True
        assert len(list(page.object_list)) == 2
