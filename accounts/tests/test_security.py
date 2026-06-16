"""Загальні тести безпеки — session, конфігурація."""

from __future__ import annotations

import pytest
from django.conf import settings


class TestSessionSecurity:
    """Тести безпеки сесій — відповідність конфігурації."""

    def test_session_cookie_httponly(self) -> None:
        """SESSION_COOKIE_HTTPONLY має бути True."""
        assert settings.SESSION_COOKIE_HTTPONLY is True

    def test_session_cookie_samesite(self) -> None:
        """SESSION_COOKIE_SAMESITE має бути Lax або Strict."""
        assert settings.SESSION_COOKIE_SAMESITE in ("Lax", "Strict")

    def test_session_expire_at_browser_close(self) -> None:
        """SESSION_EXPIRE_AT_BROWSER_CLOSE має бути True."""
        assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is True

    def test_session_cookie_age(self) -> None:
        """SESSION_COOKIE_AGE має бути 8 годин або менше."""
        assert settings.SESSION_COOKIE_AGE <= 28800
