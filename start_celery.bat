@echo off
REM Скрипт запуска Celery worker для Windows
echo ========================================
echo Запуск Celery Worker
echo ========================================

REM Проверка виртуального окружения
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM Переход в директорию проекта
cd autotest_ui

REM Запуск Celery
echo Запуск Celery worker...
celery -A autotest_ui worker -l info --pool=solo

pause
