from django.contrib import admin

from accounts.models import Employee, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Налаштування адміністративного інтерфейсу для моделі Role."""

    list_display = ['codename', 'name']
    search_fields = ['codename', 'name']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """Налаштування адміністративного інтерфейсу для моделі Employee."""

    list_display = [
        'user',
        'company',
        'roles_display',
        'phone',
        'is_active',
        'created_at',
    ]
    list_filter = ['roles', 'is_active', 'company']
    search_fields = ['user__username', 'user__email', 'phone']
    list_select_related = ['user', 'company']
    filter_horizontal = ['roles']

    @admin.display(description='Ролі')
    def roles_display(self, obj: Employee) -> str:
        """Відображає ролі співробітника через кому."""
        return ', '.join(r.name for r in obj.roles.all())
