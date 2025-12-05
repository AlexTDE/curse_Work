from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import CoverageMetric, Defect, Run, TestCase, UIElement
from .cv_utils import (
    classify_element_type,
    detect_elements_improved,
    load_image,
    analyze_elements_diff,
    compute_diff_mask,
)
try:
    from .ml_classifier import predict_element_type, is_model_trained
except ImportError:
    # Если scikit-learn не установлен, используем заглушки
    def is_model_trained():
        return False
    def predict_element_type(img, bbox, img_width, img_height, fallback_type='unknown'):
        return fallback_type, 0.0
import cv2
import numpy as np
import os
import json

@shared_task(bind=True)
def generate_test_from_screenshot(self, testcase_id):
    """
    1) Загружает reference_screenshot (по path)
    2) Использует улучшенное детектирование элементов (несколько методов)
    3) Классифицирует тип каждого элемента (button, input, label, image, link)
    4) Извлекает текст с помощью OCR (если доступно)
    5) Сохраняет UIElement для каждого bbox (в относительных координатах)
    6) Помечает TestCase.status = 'analyzed'
    """
    try:
        tc = TestCase.objects.get(pk=testcase_id)
    except TestCase.DoesNotExist:
        return {'error': 'TestCase not found', 'id': testcase_id}

    # получаем путь к файлу
    if not tc.reference_screenshot:
        return {'error': 'No reference screenshot', 'id': testcase_id}

    img_path = tc.reference_screenshot.path
    if not os.path.exists(img_path):
        return {'error': 'File not found', 'path': img_path}

    # Загружаем изображение
    img = load_image(img_path)
    if img is None:
        return {'error': 'cv2.imread failed', 'path': img_path}

    h, w = img.shape[:2]

    # Используем улучшенное детектирование элементов
    # detect_elements_improved использует YOLOv8 (если доступен) и несколько методов детектирования
    # и автоматически удаляет дубликаты
    # Можно настроить использование YOLOv8 через параметры use_yolo и yolo_conf_threshold
    use_yolo = getattr(settings, 'USE_YOLO_DETECTION', True)
    yolo_conf = getattr(settings, 'YOLO_CONF_THRESHOLD', 0.15)  # Снижен порог для лучшего обнаружения
    elements_data = detect_elements_improved(img, use_yolo=use_yolo, yolo_conf_threshold=yolo_conf)

    # Очистим старые элементы для этого TestCase
    tc.elements.all().delete()

    saved = 0
    total_pixels = w * h
    for elem_data in elements_data:
        bbox = elem_data['bbox']
        confidence = elem_data['confidence']
        abs_w = max(1, int(bbox['w'] * w))
        abs_h = max(1, int(bbox['h'] * h))
        area_px = abs_w * abs_h
        aspect_ratio = abs_w / max(abs_h, 1)
        relative_area = area_px / total_pixels
        is_small = relative_area < 0.001  # Маленький элемент
        
        # Классифицируем тип элемента (button, input, label, image, link, unknown)
        # Если YOLOv8 предоставил класс, используем его, иначе используем ML или эвристики
        element_type = 'unknown'
        type_confidence = 0.0
        
        # Проверяем, есть ли класс от YOLOv8
        if 'class_name' in elem_data and elem_data['class_name'] != 'unknown':
            element_type = elem_data['class_name']
            type_confidence = elem_data.get('confidence', 0.5)
            # Маппинг классов YOLOv8 на стандартные типы элементов UI
            yolo_to_ui_type = {
                'button': 'button',
                'input': 'input',
                'text': 'label',
                'label': 'label',
                'image': 'image',
                'link': 'link',
                'icon': 'image',
            }
            # Пытаемся найти соответствие (case-insensitive)
            class_name_lower = element_type.lower()
            if class_name_lower in yolo_to_ui_type:
                element_type = yolo_to_ui_type[class_name_lower]
        
        # Если YOLOv8 не дал класс или уверенность низкая, используем ML или эвристики
        if element_type == 'unknown' or type_confidence < 0.5:
            if is_model_trained():
                ml_type, ml_conf = predict_element_type(img, bbox, w, h, fallback_type='unknown')
                # Если ML дала лучшую уверенность, используем её
                if ml_conf > type_confidence:
                    element_type = ml_type
                    type_confidence = ml_conf
            else:
                heuristic_type, heuristic_conf = classify_element_type(img, bbox, w, h)
                if heuristic_conf > type_confidence:
                    element_type = heuristic_type
                    type_confidence = heuristic_conf
        
        # OCR убран - используем только визуальные признаки и класс элемента от YOLO
        else:
            # Если нет текста и элемент похож на input по форме
            if element_type == 'unknown' and aspect_ratio > 3.0 and abs_h < 50:
                element_type = 'input'
                type_confidence = 0.6
        
        # Финальная коррекция на основе формы и размера
        # Если элемент очень широкий и невысокий - скорее всего input, а не button
        if element_type == 'button' and aspect_ratio > 5.0 and abs_h < 40:
            element_type = 'input'
            type_confidence = max(type_confidence, 0.75)
        
        # Если элемент квадратный и маленький - скорее всего button
        if element_type in ('label', 'unknown') and 0.7 <= aspect_ratio <= 1.3 and is_small:
            element_type = 'button'
            type_confidence = max(type_confidence, 0.7)
        
        # Если элемент unknown, но имеет признаки текста - классифицируем как label
        if element_type == 'unknown':
            # Признаки текстового элемента: широкий, низкий контраст, нет границ
            if aspect_ratio > 1.5 and 0.0005 <= relative_area <= 0.15:
                # Проверяем визуальные признаки текста
                # Текст обычно имеет низкий контраст и мало краев
                # Используем данные из classify_element_type
                if aspect_ratio > 2.0:
                    element_type = 'label'
                    type_confidence = 0.65
                elif aspect_ratio > 1.5:
                    element_type = 'label'
                    type_confidence = 0.6
            
            # Если элемент с границами и правильной формой - button
            if 0.5 <= aspect_ratio <= 3.0 and 0.0005 <= relative_area <= 0.1:
                element_type = 'button'
                type_confidence = 0.6

        # OCR убран - используем только тип элемента для имени
        display_name = f"{element_type or 'element'} #{saved + 1}"
        
        # Обновляем confidence с учетом классификации
        final_confidence = (confidence + type_confidence) / 2.0

        UIElement.objects.create(
            testcase=tc,
            name=display_name,
            text='',  # OCR убран - текст не извлекается
            element_type=element_type,
            bbox=bbox,
            confidence=float(final_confidence)
        )
        saved += 1

    # Если ничего не найдено — логируем предупреждение
    if saved == 0:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"No elements found for testcase {testcase_id}. Image size: {w}x{h}")
    
    # Помечаем как analyzed в любом случае
    tc.status = 'analyzed'
    tc.save(update_fields=['status'])

    return {'status': 'done', 'elements_saved': saved, 'image_size': f'{w}x{h}'}


@shared_task(bind=True)
def compare_reference_with_actual(self, run_id):
    try:
        run = Run.objects.select_related('testcase').get(pk=run_id)
    except Run.DoesNotExist:
        return {'error': 'Run not found', 'id': run_id}

    testcase = run.testcase
    if not (testcase.reference_screenshot and run.actual_screenshot):
        run.status = 'failed'
        run.error_message = 'Missing screenshots for comparison'
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'error_message', 'finished_at'])
        return {'error': 'missing screenshots', 'run': run_id}

    reference_path = testcase.reference_screenshot.path
    actual_path = run.actual_screenshot.path
    if not os.path.exists(reference_path) or not os.path.exists(actual_path):
        run.status = 'failed'
        run.error_message = 'Screenshot file not found'
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'error_message', 'finished_at'])
        return {'error': 'file not found'}

    reference = load_image(reference_path)
    actual = load_image(actual_path)
    if reference is None or actual is None:
        run.status = 'failed'
        run.error_message = 'cv2.imread failed'
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'error_message', 'finished_at'])
        return {'error': 'cv2 error'}

    h, w = reference.shape[:2]
    actual_resized = cv2.resize(actual, (w, h))

    aligned_actual, diff_mask, ssim_score = compute_diff_mask(
        reference,
        actual_resized,
        diff_threshold=getattr(settings, 'CV_DIFF_TOLERANCE', 0.12),
    )
    mismatched_pixels = int(np.count_nonzero(diff_mask))
    total_pixels = diff_mask.size
    mismatch_ratio = mismatched_pixels / max(1, total_pixels)
    diff_threshold = getattr(settings, 'CV_DIFF_TOLERANCE', 0.12)

    total_elements = testcase.elements.count()
    matched_elements = int(max(0, total_elements * (1 - mismatch_ratio)))
    mismatched_elements = max(0, total_elements - matched_elements)
    coverage_percent = 0.0 if total_elements == 0 else (matched_elements / total_elements) * 100

    element_diagnostics = analyze_elements_diff(
        testcase,
        diff_mask,
        missing_threshold=min(0.95, diff_threshold + 0.45),
        changed_threshold=max(0.15, getattr(settings, 'CV_ELEMENT_DIFF_RATIO', 0.12)),
        min_ratio=getattr(settings, 'CV_ELEMENT_DIFF_RATIO', 0.12),
        max_shift_px=getattr(settings, 'CV_ELEMENT_SHIFT_PX', 18),
    )
    try:
        run.details = json.dumps(element_diagnostics, ensure_ascii=False)
    except TypeError:
        run.details = ''

    CoverageMetric.objects.update_or_create(
        run=run,
        defaults={
            'total_elements': total_elements,
            'matched_elements': matched_elements,
            'mismatched_elements': mismatched_elements,
            'coverage_percent': coverage_percent,
        },
    )

    if ssim_score < getattr(settings, 'CV_SSIM_THRESHOLD', 0.88) or mismatch_ratio > diff_threshold:
        defect = Defect.objects.create(
            testcase=testcase,
            run=run,
            description='UI deviation exceeds threshold',
            severity='major' if ssim_score > 0.78 else 'critical',
            metadata={
                'mismatch_ratio': mismatch_ratio,
                'ssim_score': ssim_score,
            },
        )
        
        # Автоматически создаем задачу в Jira, если настроено
        try:
            from .jira_integration import sync_defect_to_jira
            jira_issue_key = sync_defect_to_jira(defect)
            if jira_issue_key:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Created Jira issue {jira_issue_key} for defect {defect.id}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to create Jira issue for defect {defect.id}: {e}")

    run.status = 'finished'
    run.finished_at = timezone.now()
    run.reference_diff_score = ssim_score
    run.coverage = coverage_percent
    run.error_message = ''
    run.save(update_fields=['status', 'finished_at', 'reference_diff_score', 'coverage', 'error_message', 'details'])

    # Отправляем callback в CI/CD систему, если есть ci_job_id
    if run.ci_job_id:
        try:
            from .ci_integration.callbacks import update_ci_status
            update_ci_status(run)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Не удалось отправить callback в CI/CD: {e}")

    return {
        'status': 'done',
        'diff_score': ssim_score,
        'coverage_percent': coverage_percent,
        'mismatch_ratio': mismatch_ratio,
    }
