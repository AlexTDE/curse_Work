"""
URL configuration for autotest_ui project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('testsystem.urls')),
    path('', include('testsystem.urls_web')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Редирект на страницу входа для неавторизованных пользователей
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib.auth.views import redirect_to_login

# Если пользователь не авторизован и пытается зайти на главную, редиректим на login
from django.conf import settings
if settings.DEBUG:
    LOGIN_URL = '/login/'
    LOGIN_REDIRECT_URL = '/'
