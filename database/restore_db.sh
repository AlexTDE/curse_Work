#!/bin/bash
# ============================================
# Скрипт восстановления базы данных из резервной копии
# ============================================

# Настройки
DB_NAME="autotest_ui"
DB_USER="autotest_user"
DB_HOST="localhost"
DB_PORT="5432"

# Проверка аргументов
if [ -z "$1" ]; then
    echo "Использование: $0 <путь_к_файлу_бэкапа>"
    echo "Пример: $0 ./backups/autotest_ui_backup_20241120_120000.sql"
    exit 1
fi

BACKUP_FILE="$1"

# Проверка существования файла
if [ ! -f "$BACKUP_FILE" ]; then
    echo "Ошибка: Файл $BACKUP_FILE не найден!"
    exit 1
fi

# Восстановление базы данных
echo "Восстановление базы данных ${DB_NAME} из ${BACKUP_FILE}..."

# Если файл .dump (бинарный формат)
if [[ "$BACKUP_FILE" == *.dump ]]; then
    PGPASSWORD="${DB_PASSWORD}" pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "$BACKUP_FILE"
else
    # Если файл .sql (текстовый формат)
    PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_FILE"
fi

if [ $? -eq 0 ]; then
    echo "База данных успешно восстановлена!"
else
    echo "Ошибка при восстановлении базы данных!"
    exit 1
fi


