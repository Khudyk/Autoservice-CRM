"""Моделі облікових записів та співробітників автосервісу.

Містить:
- Role — довідник ролей для розмежування прав доступу.
- Employee — співробітник з прив'язкою до компанії та набором ролей.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models


class Role(models.Model):
    """Модель ролі співробітника.

    Кожен співробітник може мати декілька ролей одночасно,
    що дозволяє гнучко розподіляти права доступу в системі.
    """

    codename = models.CharField(
        'Код',
        max_length=20,
        unique=True,
        help_text='Унікальний ідентифікатор ролі (director, manager, ...)',
    )
    name = models.CharField(
        'Назва',
        max_length=50,
        help_text='Людиночитана назва ролі (Директор, Менеджер, ...)',
    )

    class Meta:
        """Налаштування моделі ролі.

        Сортування за назвою для зручного відображення у формах
        та списках.
        """
        verbose_name = 'Роль'
        verbose_name_plural = 'Ролі'
        ordering = ['name']

    def __str__(self) -> str:
        """Повертає назву ролі."""
        return self.name


class Employee(models.Model):
    """Модель співробітника з прив'язкою до компанії та набором ролей."""

    class RoleChoices(models.TextChoices):
        """Константи для кодів ролей (використовуються в коді та seed-файлах)."""
        DIRECTOR = 'director', 'Директор'
        MANAGER = 'manager', 'Менеджер'
        MECHANIC = 'mechanic', 'Майстер'
        ACCOUNTANT = 'accountant', 'Бухгалтер'
        ADMIN = 'admin', 'Адміністратор'
        PURCHASER = 'purchaser', 'Закупівельник'
        STOREKEEPER = 'storekeeper', 'Складовщик'

    user: User = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee',
        verbose_name='Користувач',
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='employees',
        verbose_name='Компанія',
    )
    roles = models.ManyToManyField(
        Role,
        verbose_name='Ролі',
        related_name='employees',
        blank=True,
    )
    phone = models.CharField('Телефон', max_length=20, blank=True)
    is_active = models.BooleanField('Активний', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Налаштування моделі співробітника.

        Унікальність пари (користувач, компанія) запобігає
        прив'язці одного облікового запису до однієї компанії
        більше ніж один раз.
        """
        verbose_name = 'Співробітник'
        verbose_name_plural = 'Співробітники'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'company'],
                name='unique_user_company',
            ),
        ]

    def __str__(self) -> str:
        """Повертає рядкове представлення: ім'я користувача — компанія."""
        full_name: str = self.user.get_full_name() or self.user.username
        return f'{full_name} — {self.company.name}'

    def has_role(self, codename: str) -> bool:
        """Перевіряє, чи має співробітник конкретну роль.

        Args:
            codename: Код ролі (наприклад 'director', 'manager').

        Returns:
            True, якщо роль призначена співробітнику.
        """
        return self.roles.filter(codename=codename).exists()

    def has_any_role(self, codenames: set[str]) -> bool:
        """Перевіряє, чи має співробітник хоча б одну з перелічених ролей.

        Args:
            codenames: Набір кодів ролей.

        Returns:
            True, якщо хоча б одна роль з набору призначена співробітнику.
        """
        return self.roles.filter(codename__in=codenames).exists()


