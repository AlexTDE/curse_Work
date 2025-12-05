# Скрипт запуска Django сервера для Windows PowerShell
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Запуск Django Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Проверка виртуального окружения
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .venv\Scripts\Activate.ps1
}

# Переход в директорию проекта
Set-Location autotest_ui

# Запуск сервера
Write-Host "Запуск Django сервера на http://localhost:8000..." -ForegroundColor Green
python manage.py runserver
