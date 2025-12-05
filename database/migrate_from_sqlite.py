#!/usr/bin/env python
"""
Скрипт для миграции данных из SQLite в PostgreSQL
Использование: python database/migrate_from_sqlite.py
"""
import os
import sys
import django
from pathlib import Path

# Добавляем путь к проекту
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / 'autotest_ui'))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autotest_ui.settings')
django.setup()

from django.db import connections
from django.core.management import call_command
from testsystem.models import TestCase, Run, UIElement, CoverageMetric, Defect
from django.contrib.auth.models import User


def migrate_data():
    """Миграция данных из SQLite в PostgreSQL"""
    
    # Подключения к базам данных
    sqlite_conn = connections['sqlite']
    postgres_conn = connections['default']
    
    print("=" * 60)
    print("Миграция данных из SQLite в PostgreSQL")
    print("=" * 60)
    
    # Проверка подключений
    try:
        with sqlite_conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            sqlite_tables = cursor.fetchone()[0]
            print(f"✓ SQLite: найдено {sqlite_tables} таблиц")
    except Exception as e:
        print(f"✗ Ошибка подключения к SQLite: {e}")
        return False
    
    try:
        with postgres_conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
            postgres_tables = cursor.fetchone()[0]
            print(f"✓ PostgreSQL: найдено {postgres_tables} таблиц")
    except Exception as e:
        print(f"✗ Ошибка подключения к PostgreSQL: {e}")
        print("  Убедитесь, что база данных создана и миграции применены")
        return False
    
    # Миграция пользователей
    print("\n[1/5] Миграция пользователей...")
    users_count = User.objects.using('sqlite').count()
    if users_count > 0:
        users = User.objects.using('sqlite').all()
        migrated_users = 0
        for user in users:
            if not User.objects.using('default').filter(username=user.username).exists():
                user.pk = None
                user.save(using='default')
                migrated_users += 1
        print(f"  Мигрировано пользователей: {migrated_users}/{users_count}")
    else:
        print("  Пользователей для миграции нет")
    
    # Миграция тест-кейсов
    print("\n[2/5] Миграция тест-кейсов...")
    testcases = TestCase.objects.using('sqlite').all()
    migrated_testcases = 0
    for tc in testcases:
        if not TestCase.objects.using('default').filter(id=tc.id).exists():
            # Сохраняем оригинальный ID
            original_id = tc.id
            tc.pk = None
            tc.save(using='default')
            # Обновляем ID если нужно сохранить оригинальный
            if original_id != tc.id:
                TestCase.objects.using('default').filter(id=tc.id).update(id=original_id)
            migrated_testcases += 1
    print(f"  Мигрировано тест-кейсов: {migrated_testcases}/{testcases.count()}")
    
    # Миграция UI элементов
    print("\n[3/5] Миграция UI элементов...")
    elements = UIElement.objects.using('sqlite').all()
    migrated_elements = 0
    for elem in elements:
        if not UIElement.objects.using('default').filter(id=elem.id).exists():
            original_id = elem.id
            elem.pk = None
            elem.save(using='default')
            if original_id != elem.id:
                UIElement.objects.using('default').filter(id=elem.id).update(id=original_id)
            migrated_elements += 1
    print(f"  Мигрировано элементов: {migrated_elements}/{elements.count()}")
    
    # Миграция прогонов
    print("\n[4/5] Миграция прогонов...")
    runs = Run.objects.using('sqlite').all()
    migrated_runs = 0
    for run in runs:
        if not Run.objects.using('default').filter(id=run.id).exists():
            original_id = run.id
            run.pk = None
            run.save(using='default')
            if original_id != run.id:
                Run.objects.using('default').filter(id=run.id).update(id=original_id)
            migrated_runs += 1
    print(f"  Мигрировано прогонов: {migrated_runs}/{runs.count()}")
    
    # Миграция метрик покрытия и дефектов
    print("\n[5/5] Миграция метрик и дефектов...")
    metrics = CoverageMetric.objects.using('sqlite').all()
    migrated_metrics = 0
    for metric in metrics:
        if not CoverageMetric.objects.using('default').filter(id=metric.id).exists():
            original_id = metric.id
            metric.pk = None
            metric.save(using='default')
            if original_id != metric.id:
                CoverageMetric.objects.using('default').filter(id=metric.id).update(id=original_id)
            migrated_metrics += 1
    print(f"  Мигрировано метрик: {migrated_metrics}/{metrics.count()}")
    
    defects = Defect.objects.using('sqlite').all()
    migrated_defects = 0
    for defect in defects:
        if not Defect.objects.using('default').filter(id=defect.id).exists():
            original_id = defect.id
            defect.pk = None
            defect.save(using='default')
            if original_id != defect.id:
                Defect.objects.using('default').filter(id=defect.id).update(id=original_id)
            migrated_defects += 1
    print(f"  Мигрировано дефектов: {migrated_defects}/{defects.count()}")
    
    print("\n" + "=" * 60)
    print("Миграция завершена успешно!")
    print("=" * 60)
    return True


if __name__ == '__main__':
    # Временно добавляем SQLite в настройки для миграции
    from django.conf import settings
    settings.DATABASES['sqlite'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'autotest_ui' / 'db.sqlite3',
    }
    
    migrate_data()


