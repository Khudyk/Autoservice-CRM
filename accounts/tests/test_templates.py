"""Тести шаблонів — перевірка коректності HTML-атрибутів."""

from __future__ import annotations

import re

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from accounts.models import Employee, Role
from company.models import Company


class TestEmployeeFormTemplate:
    """Тести шаблону accounts/form.html — атрибути чекбоксів ролей."""

    @pytest.fixture
    def admin_logged_client(
        self,
        client: Client,
        db: None,
        roles: None,
    ) -> Client:
        """Створює авторизованого адміністратора."""
        user: User = User.objects.create_user(
            username='admin_user',
            password='testpass123',
            is_staff=False,
        )
        company: Company = Company.objects.create(name='Тестова компанія')
        emp = Employee.objects.create(user=user, company=company)
        emp.roles.set([Role.objects.get(codename='admin')])
        client.login(username='admin_user', password='testpass123')
        return client

    def test_role_checkboxes_have_non_empty_for_attribute(
        self,
        admin_logged_client: Client,
    ) -> None:
        """Перевіряє, що кожен чекбокс ролі має непустий атрибут for.

        Це запобігає регресу після змін у генерації id.
        """
        url: str = reverse('employee_create')
        response = admin_logged_client.get(url)
        content: str = response.content.decode()

        # Знаходимо всі label з класом role-chip (один на кожну роль)
        label_pattern: re.Pattern = re.compile(
            r'<label\s+class="role-chip[^"]*"\s+for="([^"]*)"',
        )
        matches: list[str] = label_pattern.findall(content)

        # Має бути 7 ролей (за замовчуванням у БД)
        assert len(matches) >= 7, (
            f'Знайдено лише {len(matches)} role-chip label, '
            f'очікувалось мінімум 7'
        )

        # Кожен for має бути непустим
        for for_attr in matches:
            assert for_attr.strip(), (
                f'Знайдено порожній for атрибут у role-chip'
            )

    def test_role_checkboxes_have_non_empty_id_attribute(
        self,
        admin_logged_client: Client,
    ) -> None:
        """Перевіряє, що кожен чекбокс ролі має непустий id."""
        url: str = reverse('employee_create')
        response = admin_logged_client.get(url)
        content: str = response.content.decode()

        # Знаходимо всі input type="checkbox" всередині role-chip
        # Атрибути можуть бути в будь-якому порядку (id може бути до або після class)
        input_pattern: re.Pattern = re.compile(
            r'<input\s[^>]*class="role-chip-input"[^>]*>',
        )
        inputs: list[str] = input_pattern.findall(content)

        assert len(inputs) >= 7, (
            f'Знайдено лише {len(inputs)} role-chip-input, '
            f'очікувалось мінімум 7'
        )

        for input_html in inputs:
            # Шукаємо id атрибут
            id_match: re.Match | None = re.search(r'id="([^"]*)"', input_html)
            assert id_match is not None, (
                f'Чекбокс role-chip не має id атрибута: {input_html[:80]}...'
            )
            assert id_match.group(1).strip(), (
                f'Чекбокс role-chip має порожній id'
            )

    def test_role_checkboxes_for_matches_id(
        self,
        admin_logged_client: Client,
    ) -> None:
        """Перевіряє, що атрибут for у label збігається з id чекбокса."""
        url: str = reverse('employee_create')
        response = admin_logged_client.get(url)
        content: str = response.content.decode()

        # Знаходимо всі пари label[for] + input[id]
        label_pattern: re.Pattern = re.compile(
            r'<label\s+class="role-chip[^"]*"\s+for="([^"]*)"',
        )
        for_attrs: list[str] = label_pattern.findall(content)

        # Знаходимо всі id з role-chip-input (id може бути до або після class)
        id_pattern: re.Pattern = re.compile(
            r'<input\s[^>]*id="([^"]*)"[^>]*class="role-chip-input"[^>]*>'
            r'|<input\s[^>]*class="role-chip-input"[^>]*id="([^"]*)"[^>]*>',
        )
        id_attrs: list[str] = []
        for match in id_pattern.finditer(content):
            id_attrs.append(match.group(1) or match.group(2))

        # Кожен for має відповідати якомусь id
        for for_attr in for_attrs:
            assert for_attr in id_attrs, (
                f'label[for="{for_attr}"] не має відповідного '
                f'input[id="{for_attr}"]'
            )

    def test_role_chips_render_when_roles_exist(
        self,
        admin_logged_client: Client,
    ) -> None:
        """Перевіряє, що при наявних ролях рендеряться role-chip label."""
        url: str = reverse('employee_create')
        response = admin_logged_client.get(url)
        content: str = response.content.decode()

        # Перевіряємо, що НЕ виводиться попередження про порожній довідник
        assert 'Довідник ролей порожній' not in content

        # Перевіряємо, що рендеряться role-chip
        assert 'role-chip' in content

    def test_role_chips_show_warning_when_no_roles(
        self,
        client: Client,
        db: None,
    ) -> None:
        """Перевіряє, що без ролей показується попередження.

        Використовуємо superuser, щоб обійти перевірку прав,
        оскільки без ролей неможливо дати admin/director role,
        але superuser проходить завдяки is_superuser=True (байпас Employee check).
        """
        # Видаляємо всі ролі
        Role.objects.all().delete()

        user: User = User.objects.create_user(
            username='norole_super',
            password='testpass123',
            is_staff=True,
            is_superuser=True,
        )
        client.login(username='norole_super', password='testpass123')

        url: str = reverse('employee_create')
        response = client.get(url)
        content: str = response.content.decode()

        assert 'Довідник ролей порожній' in content
