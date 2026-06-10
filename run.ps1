# Запуск Django сервера з правильним кодуванням UTF-8 для української мови
# Використовуй: powershell -ExecutionPolicy Bypass -File run.ps1

# Встановлюємо UTF-8 для консолі PowerShell
[Console]::OutputEncoding = [Text.Encoding]::UTF8

# Встановлюємо змінну середовища для Python (додатковий захист)
$env:PYTHONIOENCODING = 'utf-8'

Write-Host "=== Запуск Django Dev Server (UTF-8) ===" -ForegroundColor Green
Write-Host "Адреса: http://127.0.0.1:8000/" -ForegroundColor Cyan

# Запускаємо сервер
python manage.py runserver

# Якщо помилка — чекаємо перед закриттям
if ($LASTEXITCODE -ne 0) {
    Write-Host "Помилка! Код: $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Натисни Enter для виходу"
}
