# 🚀 Полное руководство по CI/CD интеграции

## 📋 Что реализовано

### ✅ Основной функционал

1. **Webhook-эндпоинты** для приема событий от CI/CD:
   - `/api/webhooks/ci/github/` - GitHub Actions
   - `/api/webhooks/ci/gitlab/` - GitLab CI
   - `/api/webhooks/ci/jenkins/` - Jenkins
   - `/api/webhooks/ci/generic/` - Универсальный webhook

2. **API для получения статусов**:
   - `GET /api/runs/?ci_job_id=<job_id>` - список прогонов по CI job ID
   - `GET /api/runs/ci-status/?ci_job_id=<job_id>` - сводка статусов
   - `GET /api/runs/<id>/ci-status-detail/` - детальный статус прогона

3. **Автоматические callback'и**:
   - После завершения прогона автоматически отправляются результаты обратно в CI/CD
   - Поддержка GitHub, GitLab, Jenkins

4. **Парсеры данных**:
   - Автоматическое извлечение информации из webhook'ов разных CI/CD систем
   - Сохранение метаданных (branch, commit, repository и т.д.)

---

## 🔧 Настройка

### Шаг 1: Переменные окружения

Добавьте в `.env` файл:

```env
# CI/CD Webhook Secrets (опционально, для безопасности)
GITHUB_WEBHOOK_SECRET=your-github-webhook-secret
GITLAB_WEBHOOK_TOKEN=your-gitlab-token
JENKINS_WEBHOOK_SECRET=your-jenkins-secret

# Настройки callback'ов
CI_CALLBACK_ENABLED=1  # 1 - включить, 0 - выключить
CI_API_BASE_URL=http://localhost:8000  # URL вашего API
```

### Шаг 2: Применение миграций

```bash
cd autotest_ui
python manage.py migrate
```

### Шаг 3: Проверка работы

```bash
# Проверьте, что все эндпоинты доступны
python manage.py check
```

---

## 📡 Использование

### Вариант 1: Через Webhook (автоматический)

CI/CD система отправляет webhook при запуске/завершении джобы.

### Вариант 2: Через API (ручной)

Создание прогона вручную через API:

```bash
curl -X POST http://localhost:8000/api/runs/ \
  -H "Content-Type: application/json" \
  -d '{
    "testcase": 1,
    "ci_job_id": "github-123456",
    "actual_screenshot": <file>
  }'
```

---

## 🔗 Интеграция с GitHub Actions

### 1. Настройка workflow

Создайте файл `.github/workflows/ui-tests.yml`:

```yaml
name: UI Visual Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

jobs:
  ui-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install selenium requests
    
    - name: Run UI tests and capture screenshots
      run: |
        python tests/ui_tests.py
    
    - name: Upload screenshots to test system
      env:
        API_URL: ${{ secrets.AUTOTEST_API_URL }}
        API_TOKEN: ${{ secrets.AUTOTEST_API_TOKEN }}
      run: |
        python scripts/upload_screenshots.py \
          --api-url $API_URL \
          --token $API_TOKEN \
          --ci-job-id ${{ github.run_id }} \
          --testcase-id 1 \
          --screenshots-dir ./screenshots
    
    - name: Wait for test results
      env:
        API_URL: ${{ secrets.AUTOTEST_API_URL }}
      run: |
        python scripts/wait_for_results.py \
          --api-url $API_URL \
          --ci-job-id ${{ github.run_id }} \
          --timeout 300
    
    - name: Get test results
      env:
        API_URL: ${{ secrets.AUTOTEST_API_URL }}
      run: |
        python scripts/get_test_results.py \
          --api-url $API_URL \
          --ci-job-id ${{ github.run_id }}
```

### 2. Настройка Secrets в GitHub

1. Перейдите в Settings → Secrets and variables → Actions
2. Добавьте:
   - `AUTOTEST_API_URL` - URL вашего API (например, `http://your-api.com`)
   - `AUTOTEST_API_TOKEN` - токен для аутентификации (опционально)

### 3. Настройка Webhook (опционально)

1. Settings → Webhooks → Add webhook
2. Payload URL: `http://your-api.com/api/webhooks/ci/github/`
3. Content type: `application/json`
4. Secret: ваш `GITHUB_WEBHOOK_SECRET`
5. Events: выберите `Workflow run`

---

## 🔗 Интеграция с GitLab CI

### 1. Настройка `.gitlab-ci.yml`

```yaml
stages:
  - test
  - ui-tests

variables:
  AUTOTEST_API_URL: "http://your-api.com"
  AUTOTEST_API_TOKEN: "${AUTOTEST_API_TOKEN}"

ui-tests:
  stage: ui-tests
  image: python:3.12
  
  before_script:
    - pip install selenium requests
  
  script:
    # Запуск тестов и захват скриншотов
    - python tests/ui_tests.py
    
    # Загрузка скриншотов
    - python scripts/upload_screenshots.py
      --api-url $AUTOTEST_API_URL
      --token $AUTOTEST_API_TOKEN
      --ci-job-id $CI_JOB_ID
      --testcase-id 1
      --screenshots-dir ./screenshots
    
    # Ожидание результатов
    - python scripts/wait_for_results.py
      --api-url $AUTOTEST_API_URL
      --ci-job-id $CI_JOB_ID
      --timeout 300
    
    # Получение результатов
    - python scripts/get_test_results.py
      --api-url $AUTOTEST_API_URL
      --ci-job-id $CI_JOB_ID
  
  artifacts:
    when: always
    paths:
      - screenshots/
      - test-results.json
    expire_in: 1 week
```

### 2. Настройка переменных в GitLab

1. Settings → CI/CD → Variables
2. Добавьте:
   - `AUTOTEST_API_URL` - URL вашего API
   - `AUTOTEST_API_TOKEN` - токен (опционально)

### 3. Настройка Webhook

1. Settings → Webhooks
2. URL: `http://your-api.com/api/webhooks/ci/gitlab/`
3. Secret token: ваш `GITLAB_WEBHOOK_TOKEN`
4. Trigger: Pipeline events

---

## 🔗 Интеграция с Jenkins

### 1. Pipeline скрипт

Создайте `Jenkinsfile`:

```groovy
pipeline {
    agent any
    
    environment {
        AUTOTEST_API_URL = 'http://your-api.com'
        AUTOTEST_API_TOKEN = credentials('autotest-api-token')
    }
    
    stages {
        stage('UI Tests') {
            steps {
                sh '''
                    pip install selenium requests
                    python tests/ui_tests.py
                '''
            }
        }
        
        stage('Upload Screenshots') {
            steps {
                sh '''
                    python scripts/upload_screenshots.py \\
                        --api-url $AUTOTEST_API_URL \\
                        --token $AUTOTEST_API_TOKEN \\
                        --ci-job-id ${JOB_NAME}-${BUILD_NUMBER} \\
                        --testcase-id 1 \\
                        --screenshots-dir ./screenshots
                '''
            }
        }
        
        stage('Wait for Results') {
            steps {
                sh '''
                    python scripts/wait_for_results.py \\
                        --api-url $AUTOTEST_API_URL \\
                        --ci-job-id ${JOB_NAME}-${BUILD_NUMBER} \\
                        --timeout 300
                '''
            }
        }
        
        stage('Get Results') {
            steps {
                sh '''
                    python scripts/get_test_results.py \\
                        --api-url $AUTOTEST_API_URL \\
                        --ci-job-id ${JOB_NAME}-${BUILD_NUMBER}
                '''
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'screenshots/**', fingerprint: true
            archiveArtifacts artifacts: 'test-results.json', fingerprint: true
        }
    }
}
```

### 2. Настройка Webhook в Jenkins

1. Установите плагин "Generic Webhook Trigger"
2. В настройках job:
   - Build Triggers → Generic Webhook Trigger
   - Post content parameters → добавьте параметры
   - Token: ваш `JENKINS_WEBHOOK_SECRET`

---

## 🧪 Тестирование интеграции

### Тест 1: Проверка webhook'ов

```bash
# Тест GitHub webhook
curl -X POST http://localhost:8000/api/webhooks/ci/github/ \
  -H "Content-Type: application/json" \
  -d '{
    "action": "workflow_run",
    "workflow_run": {
      "id": 123456,
      "name": "UI Tests",
      "status": "completed",
      "conclusion": "success",
      "head_branch": "main",
      "head_sha": "abc123",
      "html_url": "https://github.com/user/repo/actions/runs/123456"
    },
    "repository": {
      "name": "my-repo",
      "full_name": "user/my-repo"
    }
  }'

# Тест GitLab webhook
curl -X POST http://localhost:8000/api/webhooks/ci/gitlab/ \
  -H "Content-Type: application/json" \
  -H "X-Gitlab-Token: your-token" \
  -d '{
    "object_kind": "pipeline",
    "object_attributes": {
      "id": 123456,
      "status": "success",
      "ref": "main",
      "sha": "abc123",
      "web_url": "https://gitlab.com/user/project/pipelines/123456"
    },
    "project": {
      "name": "my-project",
      "path_with_namespace": "user/my-project"
    }
  }'

# Тест Generic webhook
curl -X POST http://localhost:8000/api/webhooks/ci/generic/ \
  -H "Content-Type: application/json" \
  -d '{
    "ci_system": "custom",
    "ci_job_id": "test-123",
    "job_name": "UI Tests",
    "status": "success",
    "branch": "main",
    "commit_sha": "abc123",
    "repository": "my-repo"
  }'
```

### Тест 2: Проверка статусов

```bash
# Получить статус по CI job ID
curl http://localhost:8000/api/runs/ci-status/?ci_job_id=test-123

# Получить список прогонов
curl http://localhost:8000/api/runs/?ci_job_id=test-123
```

### Тест 3: Создание прогона через API

```bash
# Создать прогон с привязкой к CI job
curl -X POST http://localhost:8000/api/runs/ \
  -H "Content-Type: multipart/form-data" \
  -F "testcase=1" \
  -F "ci_job_id=test-123" \
  -F "actual_screenshot=@screenshot.png"
```

---

## 📊 Мониторинг и логи

### Просмотр логов

```bash
# Логи Django
tail -f logs/django.log

# Логи Celery
tail -f logs/celery.log
```

### Проверка статусов через админку

1. Откройте http://localhost:8000/admin/
2. Перейдите в "Runs"
3. Фильтруйте по `ci_job_id`

---

## 🔍 Отладка

### Проблема: Webhook не принимается

**Решение:**
1. Проверьте CSRF (webhook'и должны быть исключены)
2. Проверьте формат данных
3. Проверьте логи Django

### Проблема: Callback не отправляется

**Решение:**
1. Проверьте `CI_CALLBACK_ENABLED=1` в настройках
2. Проверьте наличие `callback_url` в metadata прогона
3. Проверьте логи Celery

### Проблема: Неправильный формат данных

**Решение:**
1. Используйте `/api/webhooks/ci/generic/` для кастомных форматов
2. Проверьте парсеры в `ci_integration/parsers.py`

---

## 📚 Дополнительные ресурсы

- Примеры скриптов: `docs/ci_integration/example-scripts/`
- Конфигурации CI/CD: `docs/ci_integration/`
- API документация: http://localhost:8000/api/ (Browsable API)

---

## ✅ Чеклист настройки

- [ ] Переменные окружения настроены
- [ ] Миграции применены
- [ ] Webhook'и настроены в CI/CD системах
- [ ] Тестовый прогон выполнен успешно
- [ ] Callback'и работают
- [ ] Логирование настроено

