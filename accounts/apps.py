from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Конфігурація додатку accounts."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Співробітники'

    def ready(self) -> None:
        """Імпортує сигнали при запуску Django."""
        import accounts.signals  # noqa: F401
