@echo off
:: Активуємо віртуальне середовище
call .venv\Scripts\activate

 
:: Перевіряємо, чи встановлені залежності (опціонально)
pip install -r requirements.txt

:: Запуск проєкту
python manage.py runserver

pause
pause