"""
Django settings for autotest_ui project.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем переменные из .env файла
env_path = BASE_DIR.parent / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # Устанавливаем переменную окружения, если её ещё нет
                if key not in os.environ:
                    os.environ[key] = value


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-change-me')
DEBUG = os.getenv('DJANGO_DEBUG', '1') == '1'
_allowed_hosts = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [host.strip() for host in _allowed_hosts.split(',') if host.strip()]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', 'http://localhost:8000').split(',')
    if origin.strip()
]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'django_filters',
    'corsheaders',
    'testsystem',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'autotest_ui.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'autotest_ui.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# PostgreSQL configuration

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'autotest_ui',
        'USER': 'postgres',
        'PASSWORD': '3431',
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'connect_timeout': 10,
        },
        'CONN_MAX_AGE': 600,  # Connection pooling
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Настройки авторизации
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', '0') == '1'
CELERY_TASK_EAGER_PROPAGATES = os.getenv('CELERY_TASK_EAGER_PROPAGATES', '0') == '1'

# Локальный режим выполнения задач (без Celery)
TASKS_FORCE_SYNC = os.getenv('TASKS_FORCE_SYNC', '1') == '1'
TASKS_FALLBACK_TO_SYNC = os.getenv('TASKS_FALLBACK_TO_SYNC', '1') == '1'
TASKS_WAIT_FOR_RESULT = float(os.getenv('TASKS_WAIT_FOR_RESULT', '0'))

# Параметры CV/сравнения
CV_SSIM_THRESHOLD = float(os.getenv('CV_SSIM_THRESHOLD', '0.88'))
CV_DIFF_TOLERANCE = float(os.getenv('CV_DIFF_TOLERANCE', '0.12'))  # 0..1
CV_ALIGNMENT_MAX_FEATURES = int(os.getenv('CV_ALIGNMENT_MAX_FEATURES', '800'))
CV_ELEMENT_SHIFT_PX = int(os.getenv('CV_ELEMENT_SHIFT_PX', '18'))
CV_ELEMENT_DIFF_RATIO = float(os.getenv('CV_ELEMENT_DIFF_RATIO', '0.12'))

# Параметры YOLOv8 детектирования
USE_YOLO_DETECTION = os.getenv('USE_YOLO_DETECTION', '1') == '1'  # Использовать ли YOLOv8 для детектирования
YOLO_CONF_THRESHOLD = float(os.getenv('YOLO_CONF_THRESHOLD', '0.25'))  # Порог уверенности (0.0-1.0)

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if origin.strip()
]

# CI/CD Integration Settings
GITHUB_WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET', '')
GITLAB_WEBHOOK_TOKEN = os.getenv('GITLAB_WEBHOOK_TOKEN', '')
JENKINS_WEBHOOK_SECRET = os.getenv('JENKINS_WEBHOOK_SECRET', '')

# API URL для callback'ов (если нужно отправлять результаты обратно в CI/CD)
CI_CALLBACK_ENABLED = os.getenv('CI_CALLBACK_ENABLED', '1') == '1'
CI_API_BASE_URL = os.getenv('CI_API_BASE_URL', 'http://localhost:8000')

# Jira Integration Settings
JIRA_URL = os.getenv('JIRA_URL', '')
JIRA_USERNAME = os.getenv('JIRA_USERNAME', '')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN', '')
JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY', '')
