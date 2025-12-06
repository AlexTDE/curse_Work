# Инструкции по применению изменений для валидации изображений

## Что было добавлено

1. **validators.py** - модуль с функцией валидации изображений
2. **models.py** - добавлена валидация к полям изображений
3. **views.py** - улучшена обработка ошибок валидации

## Шаги для применения изменений

### 1. Обновите код из репозитория

```bash
git pull origin main
```

### 2. Создайте и примените миграции базы данных

```bash
# Активируйте виртуальное окружение (если не активировано)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Создайте миграции
python manage.py makemigrations testsystem

# Примените миграции
python manage.py migrate testsystem
```

### 3. Перезапустите сервер

```bash
# Остановите текущий сервер (Ctrl+C)

# Запустите снова
python manage.py runserver
```

### 4. Перезапустите Celery worker

```bash
# В отдельном терминале
celery -A autotest_ui worker --loglevel=info
```

## Что изменилось

### Валидация изображений

Теперь при загрузке файлов в следующие поля:
- `TestCase.reference_screenshot`
- `Run.actual_screenshot`
- `Defect.screenshot`

Выполняются следующие проверки:

1. **Проверка расширения файла**
   - Разрешены: JPG, JPEG, PNG, GIF, BMP, WebP, TIFF
   - Запрещены: PDF, DOC, TXT и другие не-изображения

2. **Проверка MIME-типа**
   - Проверяется `Content-Type` загружаемого файла

3. **Проверка содержимого**
   - Фактическое содержимое файла проверяется с помощью `imghdr`
   - Защита от переименования файлов (например, `.pdf` в `.jpg`)

4. **Проверка размера**
   - Максимальный размер: 10 MB

### Обработка ошибок

При попытке загрузить неподдерживаемый файл:

**API ответ (JSON):**
```json
{
  "reference_screenshot": [
    "Неподдерживаемый формат файла 'pdf'. Разрешены только изображения: JPG, JPEG, PNG, GIF, BMP, WEBP, TIFF"
  ]
}
```

**HTTP статус:** `400 Bad Request`

**Результат:** Тест-кейс или прогон НЕ создаётся

## Тестирование

### Тест 1: Попытка загрузить PDF

```bash
curl -X POST http://localhost:8000/api/testcases/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -F "title=Test Case" \
  -F "reference_screenshot=@document.pdf"
```

**Ожидаемый результат:** Ошибка валидации

### Тест 2: Загрузка корректного изображения

```bash
curl -X POST http://localhost:8000/api/testcases/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -F "title=Test Case" \
  -F "reference_screenshot=@screenshot.png"
```

**Ожидаемый результат:** Тест-кейс успешно создан

### Тест 3: Переименованный файл

```bash
# Переименуйте document.pdf в fake.jpg
mv document.pdf fake.jpg

curl -X POST http://localhost:8000/api/testcases/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -F "title=Test Case" \
  -F "reference_screenshot=@fake.jpg"
```

**Ожидаемый результат:** Ошибка валидации (содержимое не соответствует изображению)

## Возможные проблемы

### Проблема: Миграции не применяются

**Решение:**
```bash
# Проверьте статус миграций
python manage.py showmigrations testsystem

# Если есть неприменённые миграции
python manage.py migrate testsystem
```

### Проблема: Ошибка импорта validators

**Решение:**
Убедитесь, что файл `validators.py` существует в `autotest_ui/testsystem/validators.py`

### Проблема: Старые файлы не проходят валидацию

**Решение:**
Валидация применяется только к НОВЫМ загрузкам. Существующие файлы в базе данных не затронуты.

## Дополнительная информация

### Изменение максимального размера файла

Откройте `autotest_ui/testsystem/validators.py` и измените:

```python
max_size = 10 * 1024 * 1024  # 10 MB
```

На желаемое значение (например, 20 MB):

```python
max_size = 20 * 1024 * 1024  # 20 MB
```

### Добавление новых форматов

В `validators.py` измените:

```python
valid_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'tif']
```

Добавьте нужные расширения в список.

## Контакты

Если возникли проблемы:
1. Проверьте логи сервера
2. Проверьте логи Celery
3. Создайте issue в репозитории
