-- ============================================
-- Скрипт удаления базы данных PostgreSQL
-- ВНИМАНИЕ: Этот скрипт удалит все данные!
-- ============================================

-- Отключение всех активных подключений к базе данных
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = 'autotest_ui'
  AND pid <> pg_backend_pid();

-- Удаление базы данных
DROP DATABASE IF EXISTS autotest_ui;

-- Удаление пользователя (опционально)
DROP USER IF EXISTS autotest_user;

-- Вывод подтверждения
SELECT 'База данных autotest_ui и пользователь autotest_user удалены' AS status;


