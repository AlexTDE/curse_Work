@echo off
REM Скрипт запуска Django сервера для Windows
echo ========================================
echo Запуск Django Server
echo ========================================

REM Проверка виртуального окружения
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM Переход в директорию проекта
cd autotest_ui

REM Запуск сервера
echo Запуск Django сервера на http://localhost:8000...
python manage.py runserver

pause
