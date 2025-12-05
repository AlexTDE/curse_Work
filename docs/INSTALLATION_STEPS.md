# 🚀 Инструкция по установке новых возможностей

## 📋 Предварительные требования

Убедитесь, что у вас установлены:
- Python 3.8+
- Django 4.0+
- PostgreSQL или SQLite
- Redis (для Celery)

---

## ✅ Шаг 1: Подтянуть изменения из Git

```bash
git pull origin main
```

Вы должны увидеть новые файлы:
- `autotest_ui/testsystem/versioning_models.py`
- `autotest_ui/testsystem/reference_versioning.py`
- `autotest_ui/testsystem/versioning_views.py`
- `autotest_ui/testsystem/analytics.py`
- `autotest_ui/testsystem/admin.py` (обновлённый)
- `docs/ADMIN_GUIDE.md`
- `docs/REFERENCE_VERSIONING_GUIDE.md`

---

## ✅ Шаг 2: Создать миграции для новых моделей

```bash
cd autotest_ui
python manage.py makemigrations
```

Вы должны увидеть:

```
Migrations for 'testsystem':
  testsystem/migrations/0002_testcaseversion_referenceupdaterequest.py
    - Create model TestCaseVersion
    - Create model ReferenceUpdateRequest
```

---

## ✅ Шаг 3: Применить миграции

```bash
python manage.py migrate
```

Вы должны увидеть:

```
Running migrations:
  Applying testsystem.0002_testcaseversion_referenceupdaterequest... OK
```

---

## ✅ Шаг 4: Обновить settings.py (если нужно)

Убедитесь, что в `autotest_ui/autotest_ui/settings.py` есть:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Ваше приложение
    'testsystem',
    
    # DRF
    'rest_framework',
    'rest_framework.authtoken',
]

# Настройки для media файлов
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

---

## ✅ Шаг 5: Обновить urls.py для админки

Откройте `autotest_ui/autotest_ui/urls.py` и **ЗАМЕНИТЕ** стандартный admin на кастомный:

```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# ИМПОРТИРУЙТЕ кастомный admin site
from testsystem.admin import admin_site

urlpatterns = [
    # ЗАМЕНИТЕ эту строку:
    # path('admin/', admin.site.urls),
    
    # НА ЭТУ:
    path('admin/', admin_site.urls),
    
    # Остальные URL
    path('api/', include('testsystem.urls')),
]

# Media files в development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## ✅ Шаг 6: Перезапустить сервер

```bash
# Остановите сервер (если он запущен)
Ctrl+C

# Запустите заново
python manage.py runserver
```

---

## ✅ Шаг 7: Проверить админ-панель

1. Откройте в браузере:
   ```
   http://localhost:8000/admin/
   ```

2. Войдите с вашими учётными данными суперпользователя

3. Теперь вы должны увидеть:

```
📊 СИСТЕМА АВТОТЕСТИРОВАНИЯ UI

🔧 AUTHENTICATION AND AUTHORIZATION
  ├─ Users
  └─ Groups

🧪 TESTSYSTEM  ← ЭТО ДОЛЖНО ПОЯВИТЬСЯ!
  ├─ Coverage metrics
  ├─ Defects
  ├─ Reference update requests  ← НОВОЕ!
  ├─ Runs
  ├─ Test case versions  ← НОВОЕ!
  ├─ Test cases
  └─ Ui elements
```

4. Проверьте аналитику:
   ```
   http://localhost:8000/admin/analytics/
   ```

---

## 🚫 Если что-то пошло не так

### Проблема 1: Ошибка при makemigrations

```bash
# Проверьте, что файл versioning_models.py есть
ls autotest_ui/testsystem/versioning_models.py

# Если есть, попробуйте:
python manage.py makemigrations testsystem
```

### Проблема 2: Не видно TESTSYSTEM в админке

Проверьте, что в `urls.py` используется `admin_site`:

```python
# НЕПРАВИЛЬНО:
# from django.contrib import admin
# path('admin/', admin.site.urls),

# ПРАВИЛЬНО:
from testsystem.admin import admin_site
path('admin/', admin_site.urls),
```

### Проблема 3: ImportError при запуске

```bash
# Проверьте синтаксис Python
python -m py_compile autotest_ui/testsystem/admin.py
python -m py_compile autotest_ui/testsystem/versioning_models.py

# Если ошибки - посмотрите в консоли, где проблема
```

### Проблема 4: 404 на /admin/analytics/

Убедитесь, что в `admin.py` есть:

```python
class CustomAdminSite(admin.AdminSite):
    # ...
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics/', self.admin_view(self.analytics_view), name='analytics'),
        ]
        return custom_urls + urls
```

---

## ✅ Проверка установки

Выполните команды:

```bash
# 1. Проверить, что модели есть в БД
python manage.py shell

>>> from testsystem.models import TestCaseVersion, ReferenceUpdateRequest
>>> print(TestCaseVersion.objects.count())
0  # Это OK - просто пока нет данных
>>> exit()

# 2. Проверить аналитику
python manage.py shell

>>> from testsystem.analytics import AnalyticsService
>>> stats = AnalyticsService.get_overall_statistics()
>>> print(stats)
{'total_testcases': 0, 'total_runs': 0, ...}  # Это OK
>>> exit()
```

---

## 🎉 Готово!

Теперь у вас есть:

✅ Версионирование эталонных скриншотов  
✅ Запросы на обновление с подтверждением  
✅ Панель аналитики  
✅ Улучшенная админ-панель с цветными бейджами  

Читайте подробнее:
- `docs/ADMIN_GUIDE.md` - руководство администратора
- `docs/REFERENCE_VERSIONING_GUIDE.md` - руководство по версионированию
