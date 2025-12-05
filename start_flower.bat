@echo off
REM Скрипт для запуска Flower на Windows

echo Starting Flower - Celery Monitoring Tool...
echo ========================================
echo.
echo Flower will be available at: http://localhost:5555
echo.
echo Flower features:
echo   - Real-time task monitoring
echo   - Task history
echo   - Worker performance monitoring
echo   - Task statistics
echo   - Task management (cancel, restart)
echo.
echo Press Ctrl+C to stop
echo ========================================
echo.

REM Change to project directory
cd autotest_ui

REM Start Flower
celery -A autotest_ui flower --port=5555 --broker=redis://localhost:6379/0 --persistent=True --db=flower.db --max_tasks=10000 --basic_auth=admin:admin123

pause
