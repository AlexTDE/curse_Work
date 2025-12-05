-- ============================================
-- Скрипт инициализации базы данных PostgreSQL
-- для системы автоматического тестирования UI
-- ============================================

-- Создание базы данных (выполняется от имени суперпользователя postgres)
-- Если база данных уже существует, этот шаг можно пропустить

-- Создание базы данных
CREATE DATABASE autotest_ui
    WITH 
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'ru_RU.UTF-8'
    LC_CTYPE = 'ru_RU.UTF-8'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1;

-- Комментарий к базе данных
COMMENT ON DATABASE autotest_ui IS 'База данных для системы автоматического тестирования UI с использованием компьютерного зрения';

-- Подключение к созданной базе данных
\c autotest_ui

-- ============================================
-- Создание пользователя и назначение прав
-- ============================================

-- Создание пользователя (если не существует)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'autotest_user') THEN
        CREATE USER autotest_user WITH PASSWORD 'autotest_password';
    END IF;
END
$$;

-- Назначение прав на базу данных
GRANT ALL PRIVILEGES ON DATABASE autotest_ui TO autotest_user;

-- Назначение прав на схему public
GRANT ALL ON SCHEMA public TO autotest_user;
GRANT CREATE ON SCHEMA public TO autotest_user;

-- Назначение прав на все таблицы (после создания таблиц Django)
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO autotest_user;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO autotest_user;

-- ============================================
-- Расширения PostgreSQL (для JSON и других функций)
-- ============================================

-- Включение расширения для работы с UUID (если нужно)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Включение расширения для полнотекстового поиска (опционально)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================
-- Комментарии
-- ============================================

COMMENT ON DATABASE autotest_ui IS 'База данных системы автоматического тестирования UI';
COMMENT ON SCHEMA public IS 'Основная схема базы данных';

-- Вывод информации о созданной базе данных
SELECT 
    datname as "Database Name",
    pg_size_pretty(pg_database_size(datname)) as "Size"
FROM pg_database 
WHERE datname = 'autotest_ui';


