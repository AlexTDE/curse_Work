# Интеграция YOLOv8 в систему автоматического тестирования UI

## Обзор

Модель YOLOv8 интегрирована в систему для детектирования UI элементов на скриншотах. Модель принимает изображение и возвращает набор bounding box'ов с названием класса, координатами и уверенностью.

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

Библиотека `ultralytics==8.3.0` уже добавлена в `requirements.txt`.

2. Убедитесь, что файл модели `yolov8s.pt` находится в папке `autotest_ui/testsystem/ml_models/`

## Настройка

В файле `.env` или в `settings.py` можно настроить следующие параметры:

| Переменная | Описание | Значение по умолчанию |
|------------|-----------|----------------------|
| `USE_YOLO_DETECTION` | Использовать ли YOLOv8 для детектирования | `1` (включено) |
| `YOLO_CONF_THRESHOLD` | Порог уверенности для детекций (0.0-1.0) | `0.25` |

Пример настройки в `.env`:
```
USE_YOLO_DETECTION=1
YOLO_CONF_THRESHOLD=0.25
```

## Использование

### Автоматическое использование

YOLOv8 автоматически используется в функции `generate_test_from_screenshot` при создании тест-кейсов из скриншотов. Система:

1. Сначала пытается использовать YOLOv8 для детектирования элементов
2. Если YOLOv8 нашел достаточно элементов (>= 12), использует только их
3. Если элементов недостаточно, комбинирует результаты YOLOv8 с эвристическими методами
4. Если YOLOv8 недоступен или произошла ошибка, использует только эвристические методы

### Программное использование

#### Детектирование элементов на изображении

```python
from testsystem.yolo_detector import detect_elements_yolo, is_yolo_available
import cv2

# Проверка доступности
if is_yolo_available():
    # Загрузка изображения
    img = cv2.imread('screenshot.png')
    
    # Детектирование элементов
    elements = detect_elements_yolo(
        img,
        conf_threshold=0.25,  # Порог уверенности
        iou_threshold=0.45,    # Порог IoU для NMS
        max_detections=300      # Максимальное количество детекций
    )
    
    # Результат: список словарей с ключами:
    # - 'bbox': {'x': float, 'y': float, 'w': float, 'h': float} (относительные координаты)
    # - 'class_name': str (название класса)
    # - 'confidence': float (уверенность 0.0-1.0)
    # - 'area': float (площадь в пикселях)
    
    for elem in elements:
        print(f"Class: {elem['class_name']}, Confidence: {elem['confidence']:.2f}")
```

#### Детектирование элементов по пути к файлу

```python
from testsystem.yolo_detector import detect_elements_yolo_from_path

elements = detect_elements_yolo_from_path(
    'path/to/screenshot.png',
    conf_threshold=0.25
)
```

#### Получение информации о модели

```python
from testsystem.yolo_detector import get_yolo_model_info

info = get_yolo_model_info()
print(info)
# {
#     'available': True,
#     'model_path': '...',
#     'exists': True,
#     'yolo_installed': True,
#     'model_type': 'YOLOv8',
#     'classes': [...],  # Список классов
#     'num_classes': N
# }
```

### Использование в cv_utils

Функция `detect_elements_improved` в `cv_utils.py` автоматически использует YOLOv8:

```python
from testsystem.cv_utils import detect_elements_improved
import cv2

img = cv2.imread('screenshot.png')

# Использование YOLOv8 (по умолчанию включено)
elements = detect_elements_improved(
    img,
    use_yolo=True,              # Использовать YOLOv8
    yolo_conf_threshold=0.25,   # Порог уверенности
    fallback_to_heuristic=True   # Использовать эвристики если YOLOv8 не дал результатов
)

# Только эвристические методы (без YOLOv8)
elements = detect_elements_improved(img, use_yolo=False)
```

## Маппинг классов

YOLOv8 возвращает названия классов, которые автоматически маппятся на стандартные типы UI элементов:

- `button` → `button`
- `input` → `input`
- `text`, `label` → `label`
- `image`, `icon` → `image`
- `link` → `link`

Если класс не найден в маппинге, используется ML-модель или эвристические методы для классификации.

## Структура файлов

```
autotest_ui/testsystem/
├── yolo_detector.py          # Модуль для работы с YOLOv8
├── cv_utils.py               # Интеграция YOLOv8 в систему детектирования
├── tasks.py                  # Использование YOLOv8 в задачах Celery
└── ml_models/
    └── yolov8s.pt           # Обученная модель YOLOv8
```

## Обработка ошибок

Система автоматически обрабатывает следующие ситуации:

1. **YOLOv8 не установлен**: Используются только эвристические методы
2. **Модель не найдена**: Используются только эвристические методы
3. **Ошибка при детектировании**: Fallback на эвристические методы
4. **Недостаточно детекций**: Комбинация YOLOv8 + эвристические методы

Все ошибки логируются, но не прерывают работу системы.

## Производительность

- YOLOv8 загружается один раз при первом использовании и кэшируется в памяти
- Детектирование одного изображения обычно занимает 0.1-0.5 секунды (зависит от размера изображения и GPU)
- Для ускорения можно использовать GPU (CUDA), если установлен PyTorch с поддержкой CUDA

## Отладка

Для проверки работы YOLOv8:

```python
from testsystem.yolo_detector import is_yolo_available, get_yolo_model_info

# Проверка доступности
print(f"YOLOv8 available: {is_yolo_available()}")

# Информация о модели
info = get_yolo_model_info()
print(f"Model info: {info}")
```

Логи работы YOLOv8 можно найти в логах Django (уровень INFO).



