"""Утиліти для мульти-тенантної ізоляції даних за компанією."""

from __future__ import annotations

from typing import Union, overload

from django.core.paginator import Paginator, Page
from django.db.models import Model, QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404

from company.models import Company


@overload
def _resolve_user(request: HttpRequest, user: None) -> object: ...


@overload
def _resolve_user(request: None, user: object) -> object: ...


def _resolve_user(request: HttpRequest | None, user: object | None) -> object:
    """Повертає user з request або з аргументу user."""
    if request is not None:
        return request.user
    return user


def get_user_company(
    request: HttpRequest | None = None,
    user: object | None = None,
) -> Company | None:
    """Повертає компанію, до якої прив'язаний користувач.

    Приймає або request, або user безпосередньо (для використання у формах).

    Args:
        request: HTTP-запит (опціонально).
        user: Користувач (опціонально, якщо request не передано).

    Returns:
        Компанія користувача або None.
    """
    current_user = _resolve_user(request, user)
    if not current_user or not current_user.is_authenticated:
        return None
    try:
        return current_user.employee.company  # type: ignore[union-attr]
    except AttributeError:
        return None


def is_admin_user(request: HttpRequest) -> bool:
    """Перевіряє, чи є користувач адміністратором (staff/superuser).

    Args:
        request: HTTP-запит.

    Returns:
        True, якщо користувач має is_staff або is_superuser.
    """
    return bool(request.user.is_authenticated and (
        request.user.is_staff or request.user.is_superuser
    ))


def filter_queryset_by_company(
    request: HttpRequest,
    queryset: QuerySet,
    field: str = 'company',
) -> QuerySet:
    """Фільтрує QuerySet за компанією поточного користувача.

    Args:
        request: HTTP-запит для визначення користувача.
        queryset: QuerySet для фільтрації.
        field: Ім'я поля компанії в моделі (за замовчуванням 'company').

    Returns:
        Відфільтрований QuerySet.
    """
    if is_admin_user(request):
        return queryset
    company: Company | None = get_user_company(request)
    if company is None:
        return queryset.none()
    return queryset.filter(**{field: company})


def get_object_or_404_for_company(
    request: HttpRequest,
    model_or_qs: Union[type[Model], QuerySet],
    field: str = 'company',
    **kwargs: object,
) -> object:
    """Повертає об'єкт, фільтруючи за компанією користувача.

    Працює як get_object_or_404, але додає фільтр за компанією.
    Приймає як клас моделі, так і QuerySet.

    Args:
        request: HTTP-запит для визначення користувача.
        model_or_qs: Клас моделі або QuerySet.
        field: Ім'я поля компанії в моделі.
        **kwargs: Додаткові фільтри для пошуку об'єкта.

    Returns:
        Знайдений об'єкт.

    Raises:
        Http404: Якщо об'єкт не знайдено.
    """
    if isinstance(model_or_qs, type) and issubclass(model_or_qs, Model):
        qs = model_or_qs.objects.all()
    else:
        qs = model_or_qs  # type: ignore[assignment]
    company: Company | None = get_user_company(request)
    if company is not None and not is_admin_user(request):
        kwargs[field] = company
    return get_object_or_404(qs, **kwargs)


def paginate_queryset(
    request: HttpRequest,
    queryset: QuerySet,
    per_page: int = 25,
    page_param: str = 'page',
) -> Page:
    """Розбиває QuerySet на сторінки та повертає об'єкт сторінки.

    Читає номер сторінки з `request.GET.get(page_param)`.
    Якщо параметр відсутній або некоректний — повертає першу сторінку.

    Args:
        request: HTTP-запит з можливим параметром `?page=`.
        queryset: QuerySet для пагінації.
        per_page: Кількість записів на сторінці (за замовчуванням 25).
        page_param: Назва GET-параметра для номера сторінки.

    Returns:
        Page: Об'єкт сторінки з ітерабельними записами.
    """
    paginator: Paginator = Paginator(queryset, per_page)
    page_number: str | None = request.GET.get(page_param)
    page_obj: Page = paginator.get_page(page_number)
    return page_obj
