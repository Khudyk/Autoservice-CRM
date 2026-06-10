from django.apps import AppConfig


class WorktypesConfig(AppConfig):
    """Конфігурація додатку worktypes."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'worktypes'
    verbose_name = 'Види робіт'
