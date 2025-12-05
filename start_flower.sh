#!/bin/bash

# Скрипт для запуска Flower - веб-интерфейса для мониторинга Celery

echo "Starting Flower - Celery Monitoring Tool..."
echo "========================================"
echo ""
echo "Flower будет доступен по адресу: http://localhost:5555"
echo ""
echo "Возможности Flower:"
echo "  - Просмотр активных задач в реальном времени"
echo "  - История выполненных задач"
echo "  - Мониторинг производительности воркеров"
echo "  - Статистика по задачам"
echo "  - Управление задачами (отмена, перезапуск)"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo "========================================"
echo ""

# Переходим в директорию проекта
cd autotest_ui

# Запускаем Flower
celery -A autotest_ui flower \
  --port=5555 \
  --broker=redis://localhost:6379/0 \
  --persistent=True \
  --db=flower.db \
  --max_tasks=10000 \
  --basic_auth=admin:admin123
