"""Middleware для кастомних 404 сторінок."""

from __future__ import annotations

from typing import Callable

from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse


class Custom404Middleware:
    """Перехоплює 404 відповіді та рендерить кастомну сторінку.

    Працює навіть при DEBUG=True.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if response.status_code == 404:
            template_response = TemplateResponse(
                request,
                '404.html',
                {'exception': 'Сторінку не знайдено'},
                status=404,
            )
            # Рендеримо перед поверненням, щоб CommonMiddleware
            # міг прочитати Content-Length без ContentNotRenderedError
            template_response.render()
            return template_response
        return response
