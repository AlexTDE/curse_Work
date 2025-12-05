"""
ML модель для классификации типов UI элементов.
Использует Random Forest на признаках, извлеченных из изображений элементов.
"""
import os
import pickle
import logging
import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional

# Безопасные импорты ML библиотек
logger = logging.getLogger(__name__)

# Безопасные импорты ML библиотек
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, accuracy_score
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("scikit-learn or joblib not installed. ML functionality disabled.")

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'ml_models', 'element_classifier.pkl')
FEATURES_PATH = os.path.join(os.path.dirname(__file__), 'ml_models', 'features_dataset.pkl')
MODEL_DIR = os.path.dirname(MODEL_PATH)
os.makedirs(MODEL_DIR, exist_ok=True)


def extract_features(img: np.ndarray, bbox: Dict[str, float], img_width: int, img_height: int) -> np.ndarray:
    """
    Извлекает признаки из области изображения для классификации.
    
    Args:
        img: Полное изображение
        bbox: Bounding box в относительных координатах
        img_width: Ширина изображения
        img_height: Высота изображения
        
    Returns:
        Вектор признаков (1D numpy array)
    """
    # Вычисляем абсолютные координаты
    x = int(bbox['x'] * img_width)
    y = int(bbox['y'] * img_height)
    w = int(bbox['w'] * img_width)
    h = int(bbox['h'] * img_height)
    
    # Извлекаем ROI
    roi = img[y:y+h, x:x+w]
    if roi.size == 0:
        return np.zeros(25)  # Возвращаем нулевой вектор если ROI пустой
    
    # Конвертируем в grayscale если нужно
    if len(roi.shape) == 3:
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        gray_roi = roi
    
    features = []
    
    # 1. Геометрические признаки
    aspect_ratio = w / max(h, 1)
    area = w * h
    total_area = img_width * img_height
    relative_area = area / total_area
    features.extend([aspect_ratio, area, relative_area, w, h])
    
    # 2. Яркость и контраст
    mean_brightness = np.mean(gray_roi)
    std_brightness = np.std(gray_roi)
    min_brightness = np.min(gray_roi)
    max_brightness = np.max(gray_roi)
    features.extend([mean_brightness, std_brightness, min_brightness, max_brightness])
    
    # 3. Анализ краев
    edges = cv2.Canny(gray_roi, 50, 150)
    edge_density = np.sum(edges > 0) / max(area, 1)
    edge_mean = np.mean(edges)
    features.extend([edge_density, edge_mean])
    
    # 4. Гистограмма (первые 5 бинов)
    hist = cv2.calcHist([gray_roi], [0], None, [5], [0, 256])
    hist = hist.flatten() / max(np.sum(hist), 1)
    features.extend(hist.tolist())
    
    # 5. Текстура (LBP-like признаки)
    # Простая мера локальной вариации
    kernel = np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]])
    if gray_roi.shape[0] > 3 and gray_roi.shape[1] > 3:
        texture = cv2.filter2D(gray_roi.astype(np.float32), -1, kernel)
        texture_mean = np.mean(np.abs(texture))
        texture_std = np.std(texture)
    else:
        texture_mean = 0
        texture_std = 0
    features.extend([texture_mean, texture_std])
    
    # 6. Цветовые признаки (если цветное изображение)
    if len(roi.shape) == 3:
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        hue_mean = np.mean(hsv[:, :, 0])
        saturation_mean = np.mean(hsv[:, :, 1])
        value_mean = np.mean(hsv[:, :, 2])
        features.extend([hue_mean, saturation_mean, value_mean])
    else:
        features.extend([0, 0, 0])
    
    # Нормализуем признаки
    features = np.array(features, dtype=np.float32)
    
    # Заполняем NaN значения
    features = np.nan_to_num(features, nan=0.0, posinf=1.0, neginf=0.0)
    
    return features


def collect_training_data(elements: List[Dict], img: np.ndarray, img_width: int, img_height: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Собирает данные для обучения из размеченных элементов.
    
    Args:
        elements: Список словарей с ключами 'bbox', 'element_type', 'confidence'
        img: Изображение
        img_width: Ширина изображения
        img_height: Высота изображения
        
    Returns:
        Tuple (X, y) где X - матрица признаков, y - метки классов
    """
    X = []
    y = []
    
    for elem in elements:
        bbox = elem.get('bbox')
        element_type = elem.get('element_type', 'unknown')
        
        if not bbox or element_type == 'unknown':
            continue
        
        features = extract_features(img, bbox, img_width, img_height)
        X.append(features)
        y.append(element_type)
    
    return np.array(X), np.array(y)


def train_model(X: np.ndarray, y: np.ndarray, test_size: float = 0.2, random_state: int = 42) -> Dict:
    """
    Обучает Random Forest классификатор.
    
    Args:
        X: Матрица признаков
        y: Метки классов
        test_size: Доля тестовой выборки
        random_state: Seed для воспроизводимости
        
    Returns:
        Словарь с метриками обучения
    """
    if not ML_AVAILABLE:
        raise ImportError("scikit-learn is not installed. Install it with: pip install scikit-learn joblib")
    
    if len(X) == 0 or len(y) == 0:
        raise ValueError("Training data is empty")
    
    # Разделяем на train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    
    # Обучаем модель
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=random_state,
        n_jobs=-1,
        class_weight='balanced'  # Балансируем классы
    )
    
    model.fit(X_train, y_train)
    
    # Оцениваем качество
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, output_dict=True)
    
    # Сохраняем модель
    joblib.dump(model, MODEL_PATH)
    logger.info(f"Model saved to {MODEL_PATH}")
    logger.info(f"Training accuracy: {accuracy:.3f}")
    
    return {
        'accuracy': accuracy,
        'report': report,
        'n_samples': len(X),
        'n_train': len(X_train),
        'n_test': len(X_test),
        'classes': list(model.classes_),
    }


def load_model():
    """Загружает обученную модель."""
    if not ML_AVAILABLE:
        return None
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        return joblib.load(MODEL_PATH)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return None


def predict_element_type(
    img: np.ndarray,
    bbox: Dict[str, float],
    img_width: int,
    img_height: int,
    fallback_type: str = 'unknown'
) -> Tuple[str, float]:
    """
    Предсказывает тип элемента с помощью ML модели.
    
    Args:
        img: Изображение
        bbox: Bounding box
        img_width: Ширина изображения
        img_height: Высота изображения
        fallback_type: Тип по умолчанию если модель не загружена
        
    Returns:
        Tuple (element_type, confidence)
    """
    model = load_model()
    if model is None:
        return fallback_type, 0.0
    
    try:
        features = extract_features(img, bbox, img_width, img_height)
        features = features.reshape(1, -1)
        
        # Предсказание
        predicted_type = model.predict(features)[0]
        probabilities = model.predict_proba(features)[0]
        
        # Находим confidence для предсказанного класса
        class_idx = list(model.classes_).index(predicted_type)
        confidence = float(probabilities[class_idx])
        
        return predicted_type, confidence
    except Exception as e:
        logger.warning(f"ML prediction failed: {e}")
        return fallback_type, 0.0


def is_model_trained() -> bool:
    """Проверяет, обучена ли модель."""
    if not ML_AVAILABLE:
        return False
    return os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 0

