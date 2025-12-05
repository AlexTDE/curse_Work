# CI/CD Integration Guide

Инструкция по использованию CI/CD интеграции для автоматического тестирования UI.

---

## 📊 Доступ к CI/CD отчётам

### Веб-интерфейс

1. **CI/CD Dashboard** - обзор всех сборок:
   ```
   http://localhost:8000/cicd/
   ```

2. **Детали сборки**:
   ```
   http://localhost:8000/cicd/job/<JOB_ID>/
   ```

### API Endpoint

Получение статуса сборки через API (для использования в CI/CD пайплайнах):

```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/cicd/status/?ci_job_id=build-123"
```

**Пример ответа:**
```json
{
  "ci_job_id": "build-123",
  "overall_status": "success",
  "total_runs": 5,
  "finished_runs": 5,
  "failed_runs": 0,
  "success_rate": 100.0,
  "runs": [
    {
      "id": 42,
      "testcase_id": 10,
      "testcase_title": "Login Page Test",
      "status": "finished",
      "coverage": 95.5,
      "defects_count": 0
    }
  ]
}
```

---

## 🔧 Интеграция с CI/CD

### 1. GitHub Actions

Создайте `.github/workflows/ui-tests.yml`:

```yaml
name: UI Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  ui-test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Take screenshot
      run: |
        # Ваш скрипт для создания скриншота
        python take_screenshot.py --url https://example.com --output screenshot.png
    
    - name: Upload to AutoTest UI
      env:
        AUTOTEST_API_URL: ${{ secrets.AUTOTEST_API_URL }}
        AUTOTEST_TOKEN: ${{ secrets.AUTOTEST_TOKEN }}
        CI_JOB_ID: ${{ github.run_id }}
      run: |
        curl -X POST "${AUTOTEST_API_URL}/api/runs/" \
          -H "Authorization: Token ${AUTOTEST_TOKEN}" \
          -F "testcase_id=1" \
          -F "actual_screenshot=@screenshot.png" \
          -F "ci_job_id=${CI_JOB_ID}" \
          -F "started_by=1"
    
    - name: Check test results
      env:
        AUTOTEST_API_URL: ${{ secrets.AUTOTEST_API_URL }}
        AUTOTEST_TOKEN: ${{ secrets.AUTOTEST_TOKEN }}
        CI_JOB_ID: ${{ github.run_id }}
      run: |
        # Ожидаем завершения тестов
        sleep 30
        
        # Получаем результаты
        STATUS=$(curl -s -H "Authorization: Token ${AUTOTEST_TOKEN}" \
          "${AUTOTEST_API_URL}/cicd/status/?ci_job_id=${CI_JOB_ID}" | \
          jq -r '.overall_status')
        
        echo "Test status: $STATUS"
        
        if [ "$STATUS" != "success" ]; then
          echo "UI tests failed!"
          exit 1
        fi
```

### 2. GitLab CI

Создайте `.gitlab-ci.yml`:

```yaml
stages:
  - test

ui-test:
  stage: test
  image: python:3.11
  
  variables:
    AUTOTEST_API_URL: "https://your-autotest-server.com"
    CI_JOB_ID: $CI_PIPELINE_ID
  
  script:
    # Создаём скриншот
    - python take_screenshot.py --url https://example.com --output screenshot.png
    
    # Загружаем в AutoTest UI
    - |
      curl -X POST "${AUTOTEST_API_URL}/api/runs/" \
        -H "Authorization: Token ${AUTOTEST_TOKEN}" \
        -F "testcase_id=1" \
        -F "actual_screenshot=@screenshot.png" \
        -F "ci_job_id=${CI_JOB_ID}"
    
    # Проверяем результаты
    - sleep 30
    - |
      STATUS=$(curl -s -H "Authorization: Token ${AUTOTEST_TOKEN}" \
        "${AUTOTEST_API_URL}/cicd/status/?ci_job_id=${CI_JOB_ID}" | \
        jq -r '.overall_status')
      
      if [ "$STATUS" != "success" ]; then
        echo "UI tests failed!"
        exit 1
      fi
```

### 3. Jenkins

```groovy
pipeline {
    agent any
    
    environment {
        AUTOTEST_API_URL = 'https://your-autotest-server.com'
        AUTOTEST_TOKEN = credentials('autotest-token')
        CI_JOB_ID = "${env.BUILD_ID}"
    }
    
    stages {
        stage('UI Test') {
            steps {
                script {
                    // Создаём скриншот
                    sh 'python take_screenshot.py --url https://example.com --output screenshot.png'
                    
                    // Загружаем в AutoTest UI
                    sh '''
                        curl -X POST "${AUTOTEST_API_URL}/api/runs/" \
                          -H "Authorization: Token ${AUTOTEST_TOKEN}" \
                          -F "testcase_id=1" \
                          -F "actual_screenshot=@screenshot.png" \
                          -F "ci_job_id=${CI_JOB_ID}"
                    '''
                    
                    // Ожидаем и проверяем
                    sleep(30)
                    
                    def response = sh(
                        script: """curl -s -H "Authorization: Token ${AUTOTEST_TOKEN}" \
                          "${AUTOTEST_API_URL}/cicd/status/?ci_job_id=${CI_JOB_ID}""",
                        returnStdout: true
                    ).trim()
                    
                    def json = readJSON text: response
                    
                    if (json.overall_status != 'success') {
                        error('UI tests failed!')
                    }
                }
            }
        }
    }
}
```

---

## 🐛 Webhooks

Система поддерживает webhooks для автоматического запуска тестов:

### GitHub Webhook
```
POST http://your-server.com/api/webhooks/ci/github/
```

### GitLab Webhook
```
POST http://your-server.com/api/webhooks/ci/gitlab/
```

### Jenkins Webhook
```
POST http://your-server.com/api/webhooks/ci/jenkins/
```

### Generic CI Webhook
```
POST http://your-server.com/api/webhooks/ci/generic/
```

**Пример payload:**
```json
{
  "ci_job_id": "build-123",
  "testcase_id": 1,
  "screenshot_url": "https://example.com/screenshot.png",
  "branch": "main",
  "commit_sha": "abc123"
}
```

---

## 📊 Метрики в CI/CD Dashboard

CI/CD Dashboard показывает:

- **Общее количество сборок** - сколько CI/CD job запустили тесты
- **Всего прогонов** - сколько тест-кейсов выполнено
- **Success Rate** - % успешных прогонов
- **Среднее покрытие** - средний % покрытия UI-элементов
- **Дефекты** - количество обнаруженных проблем

Фильтры:
- Период: 7, 14, 30, 90 дней
- Статус: все, завершёно, ошибка, в процессе

---

## ✅ Best Practices

1. **Используйте уникальные CI Job ID**:
   - GitHub: `${{ github.run_id }}`
   - GitLab: `$CI_PIPELINE_ID`
   - Jenkins: `${env.BUILD_ID}`

2. **Добавьте таймаут** для ожидания результатов

3. **Обрабатывайте ошибки** и проверяйте статусы

4. **Сохраняйте скриншоты** как артефакты CI/CD для дебага

5. **Настройте уведомления** при падении тестов

---

## 📝 Пример полного рабочего процесса

1. **Разработчик делает push** в репозиторий
2. **CI/CD запускает пайплайн**
3. **Пайплайн создаёт скриншот** приложения
4. **Скриншот отправляется** в AutoTest UI API
5. **AutoTest UI сравнивает** с эталоном
6. **Результаты возвращаются** в CI/CD
7. **CI/CD пайплайн завершается** с success/failure
8. **Команда просматривает детали** в CI/CD Dashboard

---

## 🔗 Полезные ссылки

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)
- [Jenkins Pipeline Documentation](https://www.jenkins.io/doc/book/pipeline/)
