"""Migrate Client.name → first_name + last_name with data migration."""
from __future__ import annotations

from django.db import migrations, models


def split_name(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    """Розділяє name на first_name та last_name.

    Правила:
    - Останнє слово name → last_name (прізвище)
    - Решта → first_name (ім'я)
    - Якщо name одне слово або юридична особа — все в first_name
    """
    Client = apps.get_model('clients', 'Client')  # noqa: N806
    for client in Client.objects.all():
        parts: list[str] = client.name.strip().split()
        if len(parts) >= 2:
            client.last_name = parts[-1]
            client.first_name = ' '.join(parts[:-1])
        else:
            client.first_name = parts[0] if parts else ''
            client.last_name = ''
        client.save(update_fields=['first_name', 'last_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0001_initial'),
    ]

    operations = [
        # 1. Додаємо нові поля
        migrations.AddField(
            model_name='client',
            name='first_name',
            field=models.CharField(
                blank=True, db_index=True, default='',
                max_length=255, verbose_name="Ім'я / Назва",
            ),
        ),
        migrations.AddField(
            model_name='client',
            name='last_name',
            field=models.CharField(
                blank=True, db_index=True, default='',
                max_length=255, verbose_name='Прізвище',
            ),
        ),
        # 2. Переносимо дані з name у new поля
        migrations.RunPython(split_name, migrations.RunPython.noop),
        # 3. Видаляємо старе поле
        migrations.RemoveField(
            model_name='client',
            name='name',
        ),
        # 4. Оновлюємо Meta.ordering
        migrations.AlterModelOptions(
            name='client',
            options={
                'ordering': ['last_name', 'first_name'],
                'verbose_name': 'Клієнт',
                'verbose_name_plural': 'Клієнти',
            },
        ),
    ]
