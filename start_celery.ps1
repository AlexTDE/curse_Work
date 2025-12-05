# Скрипт запуска Celery worker для Windows PowerShell
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Запуск Celery Worker" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Проверка виртуального окружения
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .venv\Scripts\Activate.ps1
}

# Переход в директорию проекта
Set-Location autotest_ui

# Запуск Celery
Write-Host "Запуск Celery worker..." -ForegroundColor Green
celery -A autotest_ui worker -l info --pool=solo
