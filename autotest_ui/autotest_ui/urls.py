"""
URL configuration for autotest_ui project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

# Импортируем кастомный admin site
from testsystem.admin import admin_site

urlpatterns = [
    # Админ-панель (кастомная с аналитикой)
    path('admin/', admin_site.urls),
    
    # API endpoints
    path('api/', include('testsystem.urls')),
]

# Пытаемся подключить веб-интерфейс
try:
    urlpatterns += [
        # Веб-интерфейс (главная страница, тест-кейсы, прогоны)
        path('', include('testsystem.urls_web')),
    ]
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Could not load web interface URLs: {e}")
    print(f"Warning: Web interface URLs not loaded: {e}")

# Media files в development режиме
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
