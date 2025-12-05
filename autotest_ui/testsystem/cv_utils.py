"""
Утилиты для компьютерного зрения: классификация элементов, OCR, улучшенное детектирование.
"""
import cv2
import numpy as np
import logging
from typing import List, Dict, Tuple, Optional, Any
from PIL import Image
from django.conf import settings
from skimage.metrics import structural_similarity

logger = logging.getLogger(__name__)

# Попытка импортировать YOLOv8 детектор
try:
    from .yolo_detector import (
        detect_elements_yolo,
        is_yolo_available,
        get_yolo_model_info
    )
    YOLO_DETECTOR_AVAILABLE = True
except ImportError:
    YOLO_DETECTOR_AVAILABLE = False
    logger.debug("YOLOv8 detector not available")

MIN_ELEMENTS_TARGET = 12
MIN_RELATIVE_AREA = 0.00002

# Попытка импортировать pytesseract (опционально)
try:
    import pytesseract

    try:
        pytesseract.get_tesseract_version()
        OCR_AVAILABLE = True
    except (pytesseract.TesseractNotFoundError, FileNotFoundError, OSError):
        OCR_AVAILABLE = False
        logger.warning("pytesseract installed, but tesseract binary not found in PATH.")
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("pytesseract not installed. OCR functionality disabled.")


def load_image(path: str) -> Optional[np.ndarray]:
    """
    Безопасно загружает изображение. Сначала пытается через cv2.imread,
    при неудаче использует Pillow (поддерживает WebP, JPEG XL и др.).
    """
    if not path:
        return None

    img = cv2.imread(path)
    if img is not None:
        return img

    try:
        with Image.open(path) as pil_img:
            pil_img = pil_img.convert('RGB')
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            logger.info("Loaded image %s via Pillow fallback", path)
            return img
    except Exception as exc:
        logger.error("Failed to load image %s: %s", path, exc)
        return None


def is_ocr_ready() -> bool:
    """Возвращает True, если OCR (tesseract) доступен для использования."""
    return OCR_AVAILABLE


def align_image(reference: np.ndarray, actual: np.ndarray, max_features: Optional[int] = None) -> Tuple[np.ndarray, bool]:
    """
    Пытается выровнять актуальный скриншот относительно эталона с помощью ORB+Homography.
    Возвращает выровненное изображение и флаг, применялась ли трансформация.
    """
    if max_features is None:
        max_features = getattr(settings, 'CV_ALIGNMENT_MAX_FEATURES', 800)

    try:
        gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
        gray_act = cv2.cvtColor(actual, cv2.COLOR_BGR2GRAY)
    except Exception as exc:
        logger.warning("align_image: failed to convert to grayscale: %s", exc)
        return actual, False

    orb = cv2.ORB_create(max_features)
    kp1, des1 = orb.detectAndCompute(gray_ref, None)
    kp2, des2 = orb.detectAndCompute(gray_act, None)

    if des1 is None or des2 is None or len(kp1) < 6 or len(kp2) < 6:
        return actual, False

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    matches = sorted(matches, key=lambda m: m.distance)[:50]

    if len(matches) < 6:
        return actual, False

    src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

    H, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
    if H is None:
        return actual, False

    aligned = cv2.warpPerspective(actual, H, (reference.shape[1], reference.shape[0]))
    return aligned, True


def compute_diff_mask(
    reference: np.ndarray,
    actual: np.ndarray,
    diff_threshold: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Строит маску различий на основе SSIM и возвращает выровненное изображение.
    """
    if diff_threshold is None:
        diff_threshold = getattr(settings, 'CV_DIFF_TOLERANCE', 0.12)

    aligned_actual, _ = align_image(reference, actual)
    gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    gray_act = cv2.cvtColor(aligned_actual, cv2.COLOR_BGR2GRAY)

    ssim_score, diff_map = structural_similarity(gray_ref, gray_act, full=True)
    diff_map = (1.0 - diff_map)
    diff_norm = cv2.normalize(diff_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    threshold_value = max(5, int(diff_threshold * 255))
    _, mask = cv2.threshold(diff_norm, threshold_value, 255, cv2.THRESH_BINARY)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    return aligned_actual, mask, float(ssim_score)


def classify_element_type(
    img: np.ndarray,
    bbox: Dict[str, float],
    original_width: int,
    original_height: int
) -> Tuple[str, float]:
    """
    Классифицирует тип элемента на основе семантического анализа.
    Использует комбинацию визуальных признаков, текста и контекста.
    
    Args:
        img: Полное изображение
        bbox: Bounding box в относительных координатах {x, y, w, h}
        original_width: Ширина исходного изображения
        original_height: Высота исходного изображения
        
    Returns:
        Tuple (element_type, confidence)
    """
    # Вычисляем абсолютные координаты с небольшим расширением для контекста
    x = max(0, int(bbox['x'] * original_width))
    y = max(0, int(bbox['y'] * original_height))
    w = max(1, int(bbox['w'] * original_width))
    h = max(1, int(bbox['h'] * original_height))
    
    # Извлекаем ROI (Region of Interest) с небольшим контекстом
    context_pad = 2
    x_start = max(0, x - context_pad)
    y_start = max(0, y - context_pad)
    x_end = min(original_width, x + w + context_pad)
    y_end = min(original_height, y + h + context_pad)
    roi = img[y_start:y_end, x_start:x_end]
    
    if roi.size == 0:
        return 'unknown', 0.0
    
    # Вычисляем характеристики
    aspect_ratio = w / max(h, 1)
    area = w * h
    total_area = original_width * original_height
    relative_area = area / total_area
    
    # Конвертируем в grayscale для анализа
    if len(roi.shape) == 3:
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # Извлекаем внутреннюю область без контекста для анализа цвета
        inner_roi = gray_roi[context_pad:context_pad+h, context_pad:context_pad+w] if roi.shape[0] > context_pad*2 and roi.shape[1] > context_pad*2 else gray_roi
    else:
        gray_roi = roi
        inner_roi = gray_roi
    
    if inner_roi.size == 0:
        inner_roi = gray_roi
    
    # Вычисляем среднюю яркость
    mean_brightness = np.mean(inner_roi)
    
    # Вычисляем контрастность (стандартное отклонение)
    contrast = np.std(inner_roi)
    
    # Анализ краев (для кнопок обычно больше краев)
    edges = cv2.Canny(inner_roi, 50, 150)
    edge_density = np.sum(edges > 0) / max(area, 1)
    
    # Анализ границ (для кнопок обычно есть четкие границы)
    # Проверяем наличие прямоугольной рамки
    border_thickness = max(1, min(3, int(min(w, h) * 0.05)))
    has_border = False
    if w > border_thickness * 2 and h > border_thickness * 2:
        # Проверяем края на наличие границы
        top_edge = inner_roi[:border_thickness, :] if inner_roi.shape[0] > border_thickness else inner_roi
        bottom_edge = inner_roi[-border_thickness:, :] if inner_roi.shape[0] > border_thickness else inner_roi
        left_edge = inner_roi[:, :border_thickness] if inner_roi.shape[1] > border_thickness else inner_roi
        right_edge = inner_roi[:, -border_thickness:] if inner_roi.shape[1] > border_thickness else inner_roi
        
        edge_std = (np.std(top_edge) + np.std(bottom_edge) + np.std(left_edge) + np.std(right_edge)) / 4
        has_border = edge_std > 15  # Четкая граница имеет высокое стандартное отклонение
    
    # Семантический анализ текста (если OCR доступен)
    # OCR убран - используем только визуальные признаки и класс элемента
    text_content = ""
    
    # Анализ размера и позиции для маленьких элементов
    is_small = relative_area < 0.001  # Очень маленький элемент
    is_very_small = relative_area < 0.0001  # Крошечный элемент (иконки, маленькие кнопки)
    is_compact = aspect_ratio >= 0.8 and aspect_ratio <= 1.2  # Квадратный или почти квадратный
    
    # OCR убран - не используем семантические ключевые слова
    
    # Классификация с учетом семантики
    
    # 1. Маленькие вспомогательные кнопки (иконки, настройки, поиск)
    if is_very_small or (is_small and is_compact):
        if has_border or edge_density > 0.15:
            return 'button', 0.85
        if contrast > 40:  # Высокий контраст характерен для кнопок
            return 'button', 0.75
    
    # 2. Input поле: обычно широкое и невысокое, светлый фон
    if aspect_ratio > 2.5 and h < original_height * 0.06:
        if mean_brightness > 220:  # Очень светлый фон
            return 'input', 0.9
        if mean_brightness > 200 and contrast < 30:  # Светлый однотонный фон
            return 'input', 0.8
    
    # 3. Кнопка: квадратная/прямоугольная, средний размер, высокий контраст, четкие границы
    # Важно: кнопки обычно имеют более высокий контраст чем надписи
    if 0.4 <= aspect_ratio <= 4.0 and 0.0005 <= relative_area <= 0.15:
        score = 0.0
        
        # Признаки кнопки
        if has_border:
            score += 0.35  # Границы - сильный признак кнопки
        if contrast > 40:  # Высокий контраст
            score += 0.25
        elif contrast > 30:
            score += 0.15
        if edge_density > 0.15:  # Много краев
            score += 0.25
        elif edge_density > 0.10:
            score += 0.15
        
        # Отрицательные признаки (это НЕ кнопка, а надпись)
        # Надписи обычно имеют низкий контраст и нет границ
        if not has_border and contrast < 25:
            score -= 0.4  # Сильный признак надписи
        
        # Если много признаков кнопки
        if score >= 0.5:
            return 'button', min(0.9, 0.5 + score * 0.4)
        
        # Если есть признаки кнопки, но не input
        if aspect_ratio < 3.0:
            if contrast > 30 and (has_border or edge_density > 0.1):
                return 'button', 0.75
            elif contrast > 25:
                return 'button', 0.65
    
    # 4. Label/Text: обычно широкое, низкий контраст, много текста, нет границ
    # Важно: надписи НЕ должны иметь границ и высокого контраста
    if aspect_ratio > 1.5:
        # Сильные признаки надписи
        if not has_border and contrast < 35:
            label_score = 0.0
            if contrast < 25:
                label_score += 0.4  # Очень низкий контраст
            if edge_density < 0.08:  # Мало краев
                label_score += 0.3
            
            if label_score >= 0.5:
                return 'label', min(0.9, 0.5 + label_score * 0.4)
        
        # Надпись обычно: широкий, низкий контраст, нет границ
        if aspect_ratio > 2.5 and not has_border and contrast < 35:
            return 'label', 0.8
        elif aspect_ratio > 1.8 and contrast < 30:
            return 'label', 0.75
    
    # 5. Image: обычно квадратное или близкое к квадрату, большой размер, высокий контраст
    if 0.6 <= aspect_ratio <= 1.4 and relative_area > 0.03:
        if contrast > 50:
            return 'image', 0.8
        if relative_area > 0.1:
            return 'image', 0.7
    
    # 6. Link: обычно небольшой, вытянутый горизонтально, может быть подчеркнут
    if aspect_ratio > 2.5 and relative_area < 0.005:
        if contrast < 25:
            return 'link', 0.6
    
    # По умолчанию - если маленький и с границами, скорее всего кнопка
    if is_small and has_border:
        return 'button', 0.6
    
    # Если элемент unknown, но имеет признаки текста (широкий, низкий контраст, нет границ)
    # классифицируем как label/text
    if aspect_ratio > 1.5 and not has_border and contrast < 40:
        # Признаки текстового элемента
        if edge_density < 0.12:  # Мало краев (текст обычно имеет меньше краев)
            return 'label', 0.65
        if aspect_ratio > 2.0 and contrast < 35:
            return 'label', 0.7
    
    # По умолчанию
    return 'unknown', 0.3


# OCR функция удалена - больше не используется


def detect_elements_improved(
    img: np.ndarray,
    use_yolo: bool = True,
    yolo_conf_threshold: float = 0.15,  # Снижен по умолчанию для лучшего обнаружения
    fallback_to_heuristic: bool = True
) -> List[Dict]:
    """
    Многоступенчатое детектирование элементов:
    - YOLOv8 (если доступен и use_yolo=True)
    - адаптивная бинаризация и градиенты
    - Canny/edge-поиск
    - MSER для текстовых областей
    - подсказки от OCR
    - grid fallback (делим экран на зоны с высокой вариативностью)
    
    Args:
        img: Изображение в формате numpy array
        use_yolo: Использовать ли YOLOv8 для детектирования (если доступен)
        yolo_conf_threshold: Порог уверенности для YOLOv8 (0.0-1.0)
        fallback_to_heuristic: Использовать ли эвристические методы если YOLOv8 не дал результатов
        
    Returns:
        Список словарей с информацией о детектированных элементах
    """
    # Улучшаем изображение для лучшей детекции
    # Увеличиваем контраст и резкость
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    
    # Применяем CLAHE (Contrast Limited Adaptive Histogram Equalization) для улучшения контраста
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Улучшаем резкость
    kernel_sharpen = np.array([[-1, -1, -1],
                               [-1,  9, -1],
                               [-1, -1, -1]])
    sharpened = cv2.filter2D(enhanced, -1, kernel_sharpen)
    
    # Объединяем улучшенное изображение обратно в BGR для YOLO
    if len(img.shape) == 3:
        img_enhanced = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
    else:
        img_enhanced = sharpened
    
    # Пытаемся использовать YOLOv8 если доступен
    if use_yolo and YOLO_DETECTOR_AVAILABLE and is_yolo_available():
        try:
            # Используем улучшенное изображение и более низкий порог для лучшего обнаружения
            # Пробуем с разными порогами для максимального покрытия
            yolo_elements = detect_elements_yolo(img_enhanced, conf_threshold=yolo_conf_threshold, iou_threshold=0.4)
            
            # Если нашли мало элементов, пробуем с еще более низким порогом
            if len(yolo_elements) < MIN_ELEMENTS_TARGET:
                logger.info(f"YOLOv8 found only {len(yolo_elements)} elements, trying lower threshold")
                yolo_elements_low = detect_elements_yolo(img_enhanced, conf_threshold=max(0.05, yolo_conf_threshold * 0.6), iou_threshold=0.35)
                # Объединяем результаты, убирая дубликаты
                h, w = img.shape[:2]
                yolo_elements = _merge_and_dedupe(yolo_elements, yolo_elements_low, w, h)
            
            if yolo_elements:
                logger.info(f"YOLOv8 detected {len(yolo_elements)} elements")
                # Конвертируем формат YOLOv8 в формат, ожидаемый системой
                converted_elements = []
                h, w = img.shape[:2]
                for elem in yolo_elements:
                    # YOLOv8 уже возвращает в правильном формате, но нужно убедиться
                    converted_elements.append({
                        'bbox': elem['bbox'],
                        'area': elem['area'],
                        'confidence': elem['confidence'],
                        'class_name': elem.get('class_name', 'unknown')
                    })
                
                # Если YOLOv8 нашел достаточно элементов, возвращаем их
                if len(converted_elements) >= MIN_ELEMENTS_TARGET or not fallback_to_heuristic:
                    return converted_elements
                
                # Иначе комбинируем с эвристическими методами
                logger.info(f"YOLOv8 found {len(converted_elements)} elements, combining with heuristic methods")
                heuristic_elements = _detect_elements_heuristic(img)
                # Объединяем результаты
                combined = _merge_and_dedupe(converted_elements, heuristic_elements, w, h)
                return combined
        except Exception as e:
            logger.warning(f"YOLOv8 detection failed, falling back to heuristic methods: {e}")
    
    # Fallback на эвристические методы
    if fallback_to_heuristic:
        return _detect_elements_heuristic(img)
    else:
        return []


def _detect_elements_heuristic(img: np.ndarray) -> List[Dict]:
    """
    Эвристическое детектирование элементов (оригинальный метод).
    Используется как fallback или в комбинации с YOLOv8.
    """
    h, w = img.shape[:2]
    total_area = max(1, w * h)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)

    short_side = min(w, h)
    kernel_small = max(3, int(short_side * 0.005))
    kernel_medium = max(kernel_small + 2, int(short_side * 0.01))
    kernel_large = max(kernel_medium + 4, int(short_side * 0.02))

    k_small = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_small, kernel_small))
    k_medium = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_medium, kernel_medium))
    k_large = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_large, kernel_large))

    contours: List[np.ndarray] = []

    def _collect(binary_img, kernel, iterations=1):
        if iterations > 0:
            processed = cv2.morphologyEx(binary_img, cv2.MORPH_CLOSE, kernel, iterations=iterations)
        else:
            processed = binary_img
        found, _ = cv2.findContours(processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours.extend(found)

    # Adaptive thresholds
    th_gauss = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY_INV, 15, 2)
    th_mean = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                    cv2.THRESH_BINARY_INV, 21, 4)
    _collect(th_gauss, k_small, iterations=2)
    _collect(th_mean, k_medium, iterations=1)

    # Top-hat / Black-hat для тонких элементов (иконки, текст)
    tophat = cv2.morphologyEx(blurred, cv2.MORPH_TOPHAT, k_small)
    blackhat = cv2.morphologyEx(blurred, cv2.MORPH_BLACKHAT, k_small)
    _, th_tophat = cv2.threshold(tophat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, th_blackhat = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _collect(th_tophat, k_small, iterations=1)
    _collect(th_blackhat, k_small, iterations=1)

    # Gradients highlight rectangular regions
    gradient = cv2.morphologyEx(blurred, cv2.MORPH_GRADIENT, k_small)
    _, grad_thresh = cv2.threshold(gradient, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _collect(grad_thresh, k_small, iterations=2)

    # Edge-based
    for low, high, kernel in [(40, 120, k_small), (20, 60, k_large)]:
        edges = cv2.Canny(blurred, low, high)
        edges = cv2.dilate(edges, kernel, iterations=1)
        _collect(edges, kernel, iterations=0)

    # MSER (text / compact regions)
    min_mser_area = max(60, int(total_area * 0.00002))
    max_mser_area = int(total_area * 0.2)
    try:
        mser = cv2.MSER_create(
            delta=5,
            min_area=min_mser_area,
            max_area=max_mser_area,
        )
    except TypeError:
        try:
            mser = cv2.MSER_create(
                _delta=5,
                _min_area=min_mser_area,
                _max_area=max_mser_area,
            )
        except Exception as exc:
            logger.debug("MSER init failed: %s", exc)
            mser = None
    if mser is not None:
        try:
            regions, _ = mser.detectRegions(blurred)
            for region in regions:
                contour = region.reshape(-1, 1, 2)
                contours.append(contour)
        except cv2.error as exc:
            logger.debug("MSER detection skipped: %s", exc)

    # Bright / dark blobs
    _, bright = cv2.threshold(enhanced, 220, 255, cv2.THRESH_BINARY)
    _, dark = cv2.threshold(enhanced, 60, 255, cv2.THRESH_BINARY_INV)
    _collect(bright, k_medium, iterations=1)
    _collect(dark, k_medium, iterations=1)

    elements = _contours_to_elements(contours, w, h, total_area, enhanced)
    elements = _remove_duplicate_elements(elements, w, h)
    elements = _merge_overlapping_elements(elements, w, h)

    if len(elements) < MIN_ELEMENTS_TARGET and OCR_AVAILABLE:
        logger.info("Using OCR-assisted detection (current=%s)", len(elements))
        # OCR убран - не используем OCR-based detection

    if len(elements) < MIN_ELEMENTS_TARGET:
        logger.info("Using grid fallback detection (current=%s)", len(elements))
        grid = _grid_fallback_detection(enhanced, w, h)
        elements = _merge_and_dedupe(elements, grid, w, h)

    logger.info("Detected %s UI elements", len(elements))
    return elements


def _contours_to_elements(
    contours: List[np.ndarray],
    w: int,
    h: int,
    total_area: int,
    gray_ref: Optional[np.ndarray] = None,
) -> List[Dict]:
    elements: List[Dict] = []
    min_area = max(30, int(total_area * MIN_RELATIVE_AREA))
    max_area = total_area * 0.8
    max_relative_area = 0.18

    for cnt in contours:
        if cnt is None or len(cnt) == 0:
            continue
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue

        x, y, ww, hh = cv2.boundingRect(cnt)
        if ww < 6 or hh < 6 or ww > w * 0.98 or hh > h * 0.98:
            continue
        
        # Коррекция координат для точности (компенсация возможного смещения)
        # Убеждаемся, что координаты в пределах изображения
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        ww = max(1, min(ww, w - x))
        hh = max(1, min(hh, h - y))

        bbox = {
            'x': float(x) / w,
            'y': float(y) / h,
            'w': float(ww) / w,
            'h': float(hh) / h
        }

        relative_area = area / total_area
        if relative_area > max_relative_area:
            continue

        if gray_ref is not None:
            roi = gray_ref[y:y+hh, x:x+ww]
            if roi.size == 0:
                continue
            roi_std = float(np.std(roi))
            if roi_std < 12:
                continue

        confidence = min(1.0, 0.4 + relative_area * 12)

        elements.append({
            'bbox': bbox,
            'area': float(area),
            'confidence': confidence
        })

    return elements


# OCR-based detection удален - больше не используется


def _grid_fallback_detection(gray: np.ndarray, w: int, h: int) -> List[Dict]:
    """
    Делим изображение на сетку и выбираем ячейки с высоким контрастом/градиентом
    как потенциальные элементы. Никогда не возвращает пустой список.
    """
    rows = 5 if h > 900 else 4
    cols = 4 if w > 1200 else 3
    variance_threshold = 18

    elements: List[Dict] = []
    for row in range(rows):
        for col in range(cols):
            x1 = int(col * w / cols)
            x2 = int((col + 1) * w / cols)
            y1 = int(row * h / rows)
            y2 = int((row + 1) * h / rows)
            cell = gray[y1:y2, x1:x2]
            if cell.size == 0:
                continue
            std = np.std(cell)
            if std < variance_threshold:
                continue

            shrink_x = int((x2 - x1) * 0.15)
            shrink_y = int((y2 - y1) * 0.15)
            x1_shrunk = min(max(x1 + shrink_x, 0), w - 1)
            y1_shrunk = min(max(y1 + shrink_y, 0), h - 1)
            x2_shrunk = max(min(x2 - shrink_x, w), x1_shrunk + 5)
            y2_shrunk = max(min(y2 - shrink_y, h), y1_shrunk + 5)

            bbox = {
                'x': float(x1_shrunk) / w,
                'y': float(y1_shrunk) / h,
                'w': float(x2_shrunk - x1_shrunk) / w,
                'h': float(y2_shrunk - y1_shrunk) / h,
            }
            confidence = min(1.0, 0.35 + std / 90.0)
            elements.append({
                'bbox': bbox,
                'area': float((x2_shrunk - x1_shrunk) * (y2_shrunk - y1_shrunk)),
                'confidence': confidence
            })

    # Если все равно пусто (очень однотонный скрин), добавим 3 крупных зоны
    if not elements:
        thirds = [1 / 3, 2 / 3]
        for tx in thirds:
            bbox = {
                'x': max(0.0, tx - 0.15),
                'y': 0.1,
                'w': 0.3,
                'h': 0.15,
            }
            elements.append({'bbox': bbox, 'area': bbox['w'] * bbox['h'] * w * h, 'confidence': 0.35})
    return elements


def _merge_and_dedupe(base: List[Dict], new: List[Dict], w: int, h: int) -> List[Dict]:
    if not new:
        return base
    combined = base + new
    combined = _remove_duplicate_elements(combined, w, h)
    combined = _merge_overlapping_elements(combined, w, h)
    return combined


def analyze_elements_diff(
    testcase: Any,
    diff_mask: np.ndarray,
    missing_threshold: float = 0.7,
    changed_threshold: float = 0.3,
    min_ratio: float = 0.04,
    min_pixels: int = 120,
    max_shift_px: int = 0,
) -> Dict[str, Any]:
    """
    Возвращает информацию о соответствии элементов: отсутствует, сдвинут, ок.

    diff_mask — бинарная маска (0/255) различий между reference и actual.
    """
    if diff_mask is None:
        return {'elements': [], 'stats': {'missing': 0, 'shifted': 0, 'ok': 0}}

    h, w = diff_mask.shape[:2]
    elements_info: List[Dict[str, Any]] = []
    stats = {'missing': 0, 'shifted': 0, 'ok': 0}

    elements_qs = getattr(testcase, 'elements', None)
    elements_iterable = elements_qs.all() if hasattr(elements_qs, 'all') else []

    padded_mask = cv2.medianBlur(diff_mask, 5)
    kernel = np.ones((3, 3), np.uint8)
    padded_mask = cv2.morphologyEx(padded_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    padded_mask = cv2.morphologyEx(padded_mask, cv2.MORPH_DILATE, kernel, iterations=1)
    pad = max(0, int(max_shift_px))

    for element in elements_iterable:
        bbox = element.bbox or {}
        ex = float(bbox.get('x', 0.0))
        ey = float(bbox.get('y', 0.0))
        ew = float(bbox.get('w', 0.0))
        eh = float(bbox.get('h', 0.0))

        x = max(0, min(int(ex * w), w - 1))
        y = max(0, min(int(ey * h), h - 1))
        width = max(1, min(int(ew * w), w - x))
        height = max(1, min(int(eh * h), h - y))

        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(w, x + width + pad)
        y1 = min(h, y + height + pad)

        roi = padded_mask[y0:y1, x0:x1]
        roi_area = max(1, roi.size)
        diff_pixels = int(np.count_nonzero(roi))
        mismatch_ratio = float(diff_pixels) / roi_area

        effective_changed = max(changed_threshold, min_ratio)
        effective_missing = max(missing_threshold, effective_changed + 0.2)
        min_pixels_missing = max(min_pixels, int(width * height * 0.15))
        min_pixels_shifted = max(int(min_pixels * 0.5), int(width * height * 0.06))

        if mismatch_ratio >= effective_missing and diff_pixels >= min_pixels_missing:
            status = 'missing'
        elif mismatch_ratio >= effective_changed and diff_pixels >= min_pixels_shifted:
            status = 'shifted'
        else:
            status = 'ok'

        stats[status] += 1

        elements_info.append({
            'id': element.id,
            'name': element.name or '',
            'text': getattr(element, 'text', '') or '',
            'type': element.element_type or 'unknown',
            'bbox': bbox,
            'diff_ratio': mismatch_ratio,
            'diff_percent': mismatch_ratio * 100.0,
            'status': status,
        })

    return {'elements': elements_info, 'stats': stats}


def _merge_overlapping_elements(elements: List[Dict], img_width: int, img_height: int) -> List[Dict]:
    """Объединяет сильно пересекающиеся элементы в один."""
    if len(elements) < 2:
        return elements

    merged = elements[:]
    changed = True
    while changed:
        changed = False
        result = []
        skip = set()
        for i in range(len(merged)):
            if i in skip:
                continue
            base = merged[i]
            x1, y1, x2, y2 = _bbox_abs(base['bbox'], img_width, img_height)
            area_base = (x2 - x1) * (y2 - y1)
            for j in range(i + 1, len(merged)):
                if j in skip:
                    continue
                other = merged[j]
                ox1, oy1, ox2, oy2 = _bbox_abs(other['bbox'], img_width, img_height)
                intersection_x1 = max(x1, ox1)
                intersection_y1 = max(y1, oy1)
                intersection_x2 = min(x2, ox2)
                intersection_y2 = min(y2, oy2)
                if intersection_x2 <= intersection_x1 or intersection_y2 <= intersection_y1:
                    continue
                intersection_area = (intersection_x2 - intersection_x1) * (intersection_y2 - intersection_y1)
                area_other = (ox2 - ox1) * (oy2 - oy1)
                union_area = area_base + area_other - intersection_area
                iou = intersection_area / max(union_area, 1)
                containment = intersection_area / max(min(area_base, area_other), 1)
                if iou > 0.6 or containment > 0.8:
                    # Объединяем
                    new_x1 = min(x1, ox1)
                    new_y1 = min(y1, oy1)
                    new_x2 = max(x2, ox2)
                    new_y2 = max(y2, oy2)
                    new_bbox = {
                        'x': new_x1 / img_width,
                        'y': new_y1 / img_height,
                        'w': (new_x2 - new_x1) / img_width,
                        'h': (new_y2 - new_y1) / img_height,
                    }
                    base = {
                        'bbox': new_bbox,
                        'area': (new_x2 - new_x1) * (new_y2 - new_y1),
                        'confidence': max(base['confidence'], other['confidence']),
                    }
                    x1, y1, x2, y2 = new_x1, new_y1, new_x2, new_y2
                    area_base = base['area']
                    skip.add(j)
                    changed = True
            result.append(base)
        merged = result
    return merged


def _bbox_abs(bbox: Dict[str, float], img_width: int, img_height: int):
    x1 = bbox['x'] * img_width
    y1 = bbox['y'] * img_height
    x2 = x1 + bbox['w'] * img_width
    y2 = y1 + bbox['h'] * img_height
    return x1, y1, x2, y2


def _remove_duplicate_elements(elements: List[Dict], img_width: int, img_height: int) -> List[Dict]:
    """
    Удаляет дубликаты элементов (пересекающиеся bbox).
    
    Args:
        elements: Список элементов
        img_width: Ширина изображения
        img_height: Высота изображения
        
    Returns:
        Отфильтрованный список элементов
    """
    if not elements:
        return []
    
    # Сортируем по confidence (убывание)
    sorted_elements = sorted(elements, key=lambda x: x['confidence'], reverse=True)
    
    filtered = []
    
    for elem in sorted_elements:
        bbox = elem['bbox']
        x1 = bbox['x'] * img_width
        y1 = bbox['y'] * img_height
        x2 = x1 + bbox['w'] * img_width
        y2 = y1 + bbox['h'] * img_height
        
        is_duplicate = False
        
        for existing in filtered:
            ex_bbox = existing['bbox']
            ex_x1 = ex_bbox['x'] * img_width
            ex_y1 = ex_bbox['y'] * img_height
            ex_x2 = ex_x1 + ex_bbox['w'] * img_width
            ex_y2 = ex_y1 + ex_bbox['h'] * img_height
            
            iou = 0.0
            # Вычисляем IoU (Intersection over Union)
            intersection_x1 = max(x1, ex_x1)
            intersection_y1 = max(y1, ex_y1)
            intersection_x2 = min(x2, ex_x2)
            intersection_y2 = min(y2, ex_y2)
            
            if intersection_x2 > intersection_x1 and intersection_y2 > intersection_y1:
                intersection_area = (intersection_x2 - intersection_x1) * (intersection_y2 - intersection_y1)
                area1 = (x2 - x1) * (y2 - y1)
                area2 = (ex_x2 - ex_x1) * (ex_y2 - ex_y1)
                union_area = area1 + area2 - intersection_area
                
                iou = intersection_area / max(union_area, 1)
                
            # Если IoU > 0.35, считаем дубликатом
            if iou > 0.35:
                is_duplicate = True
                break
        
        if not is_duplicate:
            filtered.append(elem)
    
    return filtered

