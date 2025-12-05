#!/bin/bash
# ============================================
# Скрипт резервного копирования базы данных
# ============================================

# Настройки
DB_NAME="autotest_ui"
DB_USER="autotest_user"
DB_HOST="localhost"
DB_PORT="5432"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/autotest_ui_backup_${TIMESTAMP}.sql"

# Создание директории для бэкапов
mkdir -p "$BACKUP_DIR"

# Выполнение резервного копирования
echo "Создание резервной копии базы данных ${DB_NAME}..."
PGPASSWORD="${DB_PASSWORD}" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F c -f "${BACKUP_FILE}.dump"

# Альтернативный вариант: SQL дамп
PGPASSWORD="${DB_PASSWORD}" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE"

echo "Резервная копия создана: ${BACKUP_FILE}"
echo "Размер файла: $(du -h "${BACKUP_FILE}" | cut -f1)"


