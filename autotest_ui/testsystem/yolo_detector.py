"""
Модуль для детектирования UI элементов с помощью YOLOv8.
Модель принимает изображение и возвращает набор bounding box'ов
с названием класса, координатами и уверенностью.
"""
import os
import logging
import numpy as np
import cv2
from typing import List, Dict, Optional, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)

# Попытка импортировать ultralytics
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("ultralytics not installed. YOLOv8 functionality disabled.")

# Путь к модели YOLOv8
MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    'ml_models',
    'yolov8s.pt'
)

# Глобальная переменная для кэширования модели
_yolo_model = None


def load_yolo_model() -> Optional[any]:
    """
    Загружает модель YOLOv8. Использует кэширование для избежания повторной загрузки.
    
    Returns:
        Загруженная модель YOLO или None если не удалось загрузить
    """
    global _yolo_model
    
    if not YOLO_AVAILABLE:
        logger.warning("YOLO not available: ultralytics not installed")
        return None
    
    if _yolo_model is not None:
        return _yolo_model
    
    if not os.path.exists(MODEL_PATH):
        logger.error(f"YOLOv8 model not found at {MODEL_PATH}")
        return None
    
    try:
        _yolo_model = YOLO(MODEL_PATH)
        logger.info(f"YOLOv8 model loaded successfully from {MODEL_PATH}")
        return _yolo_model
    except Exception as e:
        logger.error(f"Failed to load YOLOv8 model: {e}")
        return None


def is_yolo_available() -> bool:
    """Проверяет, доступна ли модель YOLOv8."""
    if not YOLO_AVAILABLE:
        return False
    if not os.path.exists(MODEL_PATH):
        return False
    return load_yolo_model() is not None


def detect_elements_yolo(
    img: np.ndarray,
    conf_threshold: float = 0.15,  # Снижен с 0.25 для лучшего обнаружения
    iou_threshold: float = 0.4,  # Снижен с 0.45 для меньшей фильтрации
    max_detections: int = 500  # Увеличен с 300 для большего количества детекций
) -> List[Dict]:
    """
    Детектирует UI элементы на изображении с помощью YOLOv8.
    
    Args:
        img: Изображение в формате numpy array (BGR, как в OpenCV)
        conf_threshold: Порог уверенности для детекций (0.0-1.0)
        iou_threshold: Порог IoU для NMS (Non-Maximum Suppression)
        max_detections: Максимальное количество детекций
        
    Returns:
        Список словарей с информацией о детектированных элементах:
        [
            {
                'bbox': {'x': float, 'y': float, 'w': float, 'h': float},  # относительные координаты
                'class_name': str,  # название класса
                'confidence': float,  # уверенность (0.0-1.0)
                'area': float  # площадь в пикселях
            },
            ...
        ]
    """
    model = load_yolo_model()
    if model is None:
        logger.warning("YOLOv8 model not available, returning empty list")
        return []
    
    if img is None or img.size == 0:
        logger.warning("Empty image provided to detect_elements_yolo")
        return []
    
    try:
        h, w = img.shape[:2]
        total_area = w * h
        
        # YOLO ожидает RGB изображение, а OpenCV использует BGR
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Выполняем детекцию
        results = model.predict(
            img_rgb,
            conf=conf_threshold,
            iou=iou_threshold,
            max_det=max_detections,
            verbose=False  # Отключаем вывод в консоль
        )
        
        elements = []
        
        # Обрабатываем результаты
        if results and len(results) > 0:
            result = results[0]  # Берем первый результат (одно изображение)
            
            # Проверяем наличие детекций
            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes
                
                for i in range(len(boxes)):
                    # Получаем координаты в формате xyxy (абсолютные)
                    box = boxes.xyxy[i].cpu().numpy()
                    x1, y1, x2, y2 = box
                    
                    # Коррекция координат для точности
                    # YOLOv8 может давать координаты с небольшим смещением влево и вверх
                    # Нужно сдвинуть правее (увеличить x1) и ниже (увеличить y1)
                    abs_w_raw = x2 - x1
                    abs_h_raw = y2 - y1
                    
                    # Коррекция смещения: сдвигаем вправо и вниз
                    # Для маленьких элементов коррекция более агрессивная
                    if abs_w_raw < 50 or abs_h_raw < 50:
                        # Для маленьких элементов: сдвиг вправо на 2-4px и вниз на 2-3px
                        correction_x_right = max(2, min(4, int(abs_w_raw * 0.08)))  # Сдвиг вправо 2-4px
                        correction_y_down = max(2, min(3, int(abs_h_raw * 0.06)))  # Сдвиг вниз 2-3px
                        x1 = max(0, min(w - 1, x1 + correction_x_right))  # Сдвигаем вправо
                        x2 = min(w, x2 + correction_x_right)  # Сохраняем ширину
                        y1 = max(0, min(h - 1, y1 + correction_y_down))  # Сдвигаем вниз
                        y2 = min(h, y2 + correction_y_down)  # Сохраняем высоту
                    else:
                        # Для больших элементов: меньший сдвиг
                        correction_x_right = max(1, min(3, int(abs_w_raw * 0.015)))
                        correction_y_down = max(1, min(2, int(abs_h_raw * 0.01)))
                        x1 = max(0, min(w - 1, x1 + correction_x_right))
                        x2 = min(w, x2 + correction_x_right)
                        y1 = max(0, min(h - 1, y1 + correction_y_down))
                        y2 = min(h, y2 + correction_y_down)
                    
                    # Получаем уверенность
                    confidence = float(boxes.conf[i].cpu().numpy())
                    
                    # Получаем класс
                    class_id = int(boxes.cls[i].cpu().numpy())
                    class_name = model.names[class_id] if hasattr(model, 'names') else f"class_{class_id}"
                    
                    # Вычисляем относительные координаты
                    abs_w = x2 - x1
                    abs_h = y2 - y1
                    
                    # Убеждаемся, что координаты в пределах изображения
                    x1 = max(0, min(x1, w - 1))
                    y1 = max(0, min(y1, h - 1))
                    x2 = max(x1 + 1, min(x2, w))
                    y2 = max(y1 + 1, min(y2, h))
                    abs_w = x2 - x1
                    abs_h = y2 - y1
                    
                    # Сохраняем в формате, совместимом с существующим кодом: x, y - левый верхний угол
                    bbox = {
                        'x': float(x1) / w,  # относительная координата x левого верхнего угла
                        'y': float(y1) / h,  # относительная координата y левого верхнего угла
                        'w': float(abs_w) / w,  # относительная ширина
                        'h': float(abs_h) / h   # относительная высота
                    }
                    
                    area = abs_w * abs_h
                    
                    elements.append({
                        'bbox': bbox,
                        'class_name': class_name,
                        'confidence': confidence,
                        'area': float(area)
                    })
        
        logger.info(f"YOLOv8 detected {len(elements)} elements")
        return elements
        
    except Exception as e:
        logger.error(f"Error during YOLOv8 detection: {e}", exc_info=True)
        return []


def detect_elements_yolo_from_path(
    image_path: str,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    max_detections: int = 300
) -> List[Dict]:
    """
    Детектирует UI элементы на изображении по пути к файлу.
    
    Args:
        image_path: Путь к файлу изображения
        conf_threshold: Порог уверенности для детекций (0.0-1.0)
        iou_threshold: Порог IoU для NMS
        max_detections: Максимальное количество детекций
        
    Returns:
        Список словарей с информацией о детектированных элементах
    """
    if not os.path.exists(image_path):
        logger.error(f"Image file not found: {image_path}")
        return []
    
    # Загружаем изображение через OpenCV
    img = cv2.imread(image_path)
    if img is None:
        logger.error(f"Failed to load image: {image_path}")
        return []
    
    return detect_elements_yolo(img, conf_threshold, iou_threshold, max_detections)


def get_yolo_model_info() -> Dict:
    """
    Возвращает информацию о загруженной модели YOLOv8.
    
    Returns:
        Словарь с информацией о модели
    """
    model = load_yolo_model()
    if model is None:
        return {
            'available': False,
            'model_path': MODEL_PATH,
            'exists': os.path.exists(MODEL_PATH),
            'yolo_installed': YOLO_AVAILABLE
        }
    
    info = {
        'available': True,
        'model_path': MODEL_PATH,
        'exists': True,
        'yolo_installed': True,
        'model_type': 'YOLOv8',
    }
    
    # Пытаемся получить дополнительную информацию о модели
    try:
        if hasattr(model, 'names'):
            info['classes'] = list(model.names.values())
            info['num_classes'] = len(model.names)
    except Exception:
        pass
    
    return info

