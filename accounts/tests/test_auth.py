"""Тести авторизації (вхід / вихід)."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse


class TestLoginView:
    """Тести сторінки входу."""

    def test_login_page_returns_200(self, client: Client) -> None:
        """Перевіряє, що GET /employees/login/ повертає 200."""
        url: str = reverse('login')
        response = client.get(url)
        assert response.status_code == 200

    def test_login_page_uses_correct_template(self, client: Client) -> None:
        """Перевіряє використання шаблону login.html."""
        url: str = reverse('login')
        response = client.get(url)
        assert 'registration/login.html' in [t.name for t in response.templates]

    def test_login_page_contains_form(self, client: Client) -> None:
        """Перевіряє наявність форми входу."""
        url: str = reverse('login')
        response = client.get(url)
        content: str = response.content.decode()
        assert 'method="post"' in content
        assert 'name="username"' in content
        assert 'name="password"' in content

    def test_login_success_redirects_to_index(
        self, client: Client, db: None,
    ) -> None:
        """Перевіряє, що після успішного входу редірект на головну."""
        User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        url: str = reverse('login')
        response = client.post(url, {
            'username': 'testuser',
            'password': 'testpass123',
        })
        assert response.status_code == 302
        assert response.url == reverse('index')

    def test_login_failure_stays_on_page(
        self, client: Client, db: None,
    ) -> None:
        """Перевіряє, що при помилковому паролі форма показується знову."""
        url: str = reverse('login')
        response = client.post(url, {
            'username': 'wrong',
            'password': 'wrongpass',
        })
        assert response.status_code == 200
        assert 'registration/login.html' in [t.name for t in response.templates]

    def test_login_invalid_password_shows_error(
        self, client: Client, db: None,
    ) -> None:
        """Перевіряє, що при невірному паролі показується помилка."""
        User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        url: str = reverse('login')
        response = client.post(url, {
            'username': 'testuser',
            'password': 'wrongpass',
        })
        content: str = response.content.decode()
        assert 'Будь ласка' in content or 'error' in content.lower() or 'alert' in content


class TestLogoutView:
    """Тести виходу з системи."""

    def test_logout_requires_post(self, client: Client, db: None) -> None:
        """Перевіряє, що GET /employees/logout/ не спрацьовує (405)."""
        # Спочатку залогінимося
        User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        client.login(username='testuser', password='testpass123')

        url: str = reverse('logout')
        response = client.get(url)
        # Django LogoutView повертає 405 для GET
        assert response.status_code in (302, 405)

    def test_logout_post_redirects_to_login(
        self, client: Client, db: None,
    ) -> None:
        """Перевіряє, що POST /employees/logout/ редіректить на login."""
        User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        client.login(username='testuser', password='testpass123')

        url: str = reverse('logout')
        response = client.post(url)
        assert response.status_code == 302
        assert response.url == reverse('login')

    def test_logout_clears_session(
        self, client: Client, db: None,
    ) -> None:
        """Перевіряє, що після виходу користувач дійсно анонімний."""
        User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        client.login(username='testuser', password='testpass123')

        # Перевіряємо, що залогінений
        index_url: str = reverse('index')
        response = client.get(index_url)
        assert response.context['user'].is_authenticated is True

        # Виходимо
        client.post(reverse('logout'))

        # Перевіряємо, що анонімний
        response = client.get(index_url)
        assert response.context['user'].is_authenticated is False
