# Ключевые функции приложения

Этот документ содержит описание основных функций системы автоматического тестирования UI с примерами кода.

---

## 1. Создание тест-кейса

**Файл:** `autotest_ui/testsystem/views.py`

**Назначение:** Создание нового тест-кейса с эталонным скриншотом и валидацией изображения.

```python
class TestCaseViewSet(viewsets.ModelViewSet):
    serializer_class = TestCaseSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'created_by']
    
    def perform_create(self, serializer):
        """
        При создании автоматически назначаем текущего пользователя как created_by
        и валидируем загруженное изображение
        """
        # Валидация изображения
        reference_screenshot = serializer.validated_data.get('reference_screenshot')
        if reference_screenshot:
            try:
                validate_image_file(reference_screenshot)
            except DjangoValidationError as e:
                raise ValidationError({'reference_screenshot': e.messages})
        
        # Сохраняем тест-кейс с привязкой к пользователю
        serializer.save(created_by=self.request.user)
```

**Ключевые особенности:**
- ✅ Автоматическая привязка к пользователю
- ✅ Валидация формата и содержимого изображения
- ✅ Проверка размера (макс. 10 MB)

---

## 2. Автоматический анализ UI элементов

**Файл:** `autotest_ui/testsystem/tasks.py`

**Назначение:** Автоматическое обнаружение и классификация UI элементов на скриншоте.

```python
@shared_task(bind=True)
def generate_test_from_screenshot(self, testcase_id):
    """
    Анализ эталонного скриншота:
    1. Загружает изображение
    2. Обнаруживает UI элементы с помощью YOLOv8 и OpenCV
    3. Классифицирует тип каждого элемента
    4. Сохраняет результаты в базу данных
    """
    try:
        tc = TestCase.objects.get(pk=testcase_id)
    except TestCase.DoesNotExist:
        return {'error': 'TestCase not found', 'id': testcase_id}

    # Загружаем изображение
    img_path = tc.reference_screenshot.path
    if not os.path.exists(img_path):
        return {'error': 'File not found', 'path': img_path}

    img = load_image(img_path)
    if img is None:
        return {'error': 'cv2.imread failed', 'path': img_path}

    h, w = img.shape[:2]

    # Используем улучшенное детектирование элементов
    # detect_elements_improved использует:
    # - YOLOv8 (если доступен)
    # - Несколько методов детектирования
    # - Автоматическое удаление дубликатов
    use_yolo = getattr(settings, 'USE_YOLO_DETECTION', True)
    yolo_conf = getattr(settings, 'YOLO_CONF_THRESHOLD', 0.15)
    elements_data = detect_elements_improved(
        img, 
        use_yolo=use_yolo, 
        yolo_conf_threshold=yolo_conf
    )

    # Очистим старые элементы
    tc.elements.all().delete()

    saved = 0
    total_pixels = w * h
    
    for elem_data in elements_data:
        bbox = elem_data['bbox']
        confidence = elem_data['confidence']
        
        # Расчёт метрик элемента
        abs_w = max(1, int(bbox['w'] * w))
        abs_h = max(1, int(bbox['h'] * h))
        area_px = abs_w * abs_h
        aspect_ratio = abs_w / max(abs_h, 1)
        relative_area = area_px / total_pixels
        is_small = relative_area < 0.001
        
        # Классификация типа элемента
        element_type = 'unknown'
        type_confidence = 0.0
        
        # 1. Проверяем класс от YOLOv8
        if 'class_name' in elem_data and elem_data['class_name'] != 'unknown':
            element_type = elem_data['class_name']
            type_confidence = elem_data.get('confidence', 0.5)
            
            # Маппинг классов YOLOv8
            yolo_to_ui_type = {
                'button': 'button',
                'input': 'input',
                'text': 'label',
                'label': 'label',
                'image': 'image',
                'link': 'link',
                'icon': 'image',
            }
            class_name_lower = element_type.lower()
            if class_name_lower in yolo_to_ui_type:
                element_type = yolo_to_ui_type[class_name_lower]
        
        # 2. Если YOLOv8 не дал класс, используем ML или эвристики
        if element_type == 'unknown' or type_confidence < 0.5:
            if is_model_trained():
                ml_type, ml_conf = predict_element_type(img, bbox, w, h)
                if ml_conf > type_confidence:
                    element_type = ml_type
                    type_confidence = ml_conf
            else:
                heuristic_type, heuristic_conf = classify_element_type(img, bbox, w, h)
                if heuristic_conf > type_confidence:
                    element_type = heuristic_type
                    type_confidence = heuristic_conf
        
        # 3. Коррекция на основе формы
        # Широкий и низкий = input
        if element_type == 'button' and aspect_ratio > 5.0 and abs_h < 40:
            element_type = 'input'
            type_confidence = max(type_confidence, 0.75)
        
        # Квадратный и маленький = button
        if element_type in ('label', 'unknown') and 0.7 <= aspect_ratio <= 1.3 and is_small:
            element_type = 'button'
            type_confidence = max(type_confidence, 0.7)
        
        # 4. Сохраняем элемент
        display_name = f"{element_type or 'element'} #{saved + 1}"
        final_confidence = (confidence + type_confidence) / 2.0

        UIElement.objects.create(
            testcase=tc,
            name=display_name,
            text='',
            element_type=element_type,
            bbox=bbox,
            confidence=float(final_confidence)
        )
        saved += 1
    
    # Помечаем как analyzed
    tc.status = 'analyzed'
    tc.save(update_fields=['status'])

    return {'status': 'done', 'elements_saved': saved, 'image_size': f'{w}x{h}'}
```

**Ключевые особенности:**
- 🤖 Использование YOLOv8 для обнаружения
- 📊 ML-классификация типов элементов
- 🛠️ Эвристические правила классификации
- 💾 Автоматическое сохранение в БД

---

## 3. Сравнение скриншотов

**Файл:** `autotest_ui/testsystem/tasks.py`

**Назначение:** Сравнение фактического скриншота с эталонным и обнаружение различий.

```python
@shared_task(bind=True)
def compare_reference_with_actual(self, run_id):
    """
    Сравнение скриншотов:
    1. Загружает эталонный и фактический скриншоты
    2. Вычисляет SSIM (структурное сходство)
    3. Создаёт маску различий
    4. Анализирует каждый UI элемент
    5. Сохраняет метрики и дефекты
    """
    try:
        run = Run.objects.select_related('testcase').get(pk=run_id)
    except Run.DoesNotExist:
        return {'error': 'Run not found', 'id': run_id}

    testcase = run.testcase
    
    # Проверка наличия скриншотов
    if not (testcase.reference_screenshot and run.actual_screenshot):
        run.status = 'failed'
        run.error_message = 'Missing screenshots for comparison'
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'error_message', 'finished_at'])
        return {'error': 'missing screenshots', 'run': run_id}

    # Загрузка изображений
    reference_path = testcase.reference_screenshot.path
    actual_path = run.actual_screenshot.path
    
    reference = load_image(reference_path)
    actual = load_image(actual_path)
    
    if reference is None or actual is None:
        run.status = 'failed'
        run.error_message = 'cv2.imread failed'
        run.finished_at = timezone.now()
        run.save()
        return {'error': 'cv2 error'}

    # Выравнивание размеров
    h, w = reference.shape[:2]
    actual_resized = cv2.resize(actual, (w, h))

    # Вычисление маски различий и SSIM
    aligned_actual, diff_mask, ssim_score = compute_diff_mask(
        reference,
        actual_resized,
        diff_threshold=getattr(settings, 'CV_DIFF_TOLERANCE', 0.12),
    )
    
    # Расчёт метрик
    mismatched_pixels = int(np.count_nonzero(diff_mask))
    total_pixels = diff_mask.size
    mismatch_ratio = mismatched_pixels / max(1, total_pixels)
    
    # Расчёт покрытия элементов
    total_elements = testcase.elements.count()
    matched_elements = int(max(0, total_elements * (1 - mismatch_ratio)))
    mismatched_elements = max(0, total_elements - matched_elements)
    coverage_percent = 0.0 if total_elements == 0 else (matched_elements / total_elements) * 100

    # Анализ каждого элемента
    element_diagnostics = analyze_elements_diff(
        testcase,
        diff_mask,
        missing_threshold=min(0.95, diff_threshold + 0.45),
        changed_threshold=max(0.15, getattr(settings, 'CV_ELEMENT_DIFF_RATIO', 0.12)),
        min_ratio=getattr(settings, 'CV_ELEMENT_DIFF_RATIO', 0.12),
        max_shift_px=getattr(settings, 'CV_ELEMENT_SHIFT_PX', 18),
    )
    
    # Сохранение диагностики
    try:
        run.details = json.dumps(element_diagnostics, ensure_ascii=False)
    except TypeError:
        run.details = ''

    # Сохранение метрик покрытия
    CoverageMetric.objects.update_or_create(
        run=run,
        defaults={
            'total_elements': total_elements,
            'matched_elements': matched_elements,
            'mismatched_elements': mismatched_elements,
            'coverage_percent': coverage_percent,
        },
    )

    # Создание дефекта, если найдены различия
    diff_threshold = getattr(settings, 'CV_DIFF_TOLERANCE', 0.12)
    ssim_threshold = getattr(settings, 'CV_SSIM_THRESHOLD', 0.88)
    
    if ssim_score < ssim_threshold or mismatch_ratio > diff_threshold:
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
        
        # Интеграция с Jira
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
            logger.warning(f"Failed to create Jira issue: {e}")

    # Обновление статуса прогона
    run.status = 'finished'
    run.finished_at = timezone.now()
    run.reference_diff_score = ssim_score
    run.coverage = coverage_percent
    run.error_message = ''
    run.save(update_fields=[
        'status', 'finished_at', 'reference_diff_score', 
        'coverage', 'error_message', 'details'
    ])

    # Callback в CI/CD
    if run.ci_job_id:
        try:
            from .ci_integration.callbacks import update_ci_status
            update_ci_status(run)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"CI/CD callback failed: {e}")

    return {
        'status': 'done',
        'diff_score': ssim_score,
        'coverage_percent': coverage_percent,
        'mismatch_ratio': mismatch_ratio,
    }
```

**Ключевые особенности:**
- 🔍 SSIM (Structural Similarity Index) для оценки сходства
- 🖌️ Попиксельное сравнение
- 📈 Расчёт метрик покрытия
- 🐛 Автоматическое создание дефектов
- 🔗 Интеграция с Jira и CI/CD

---

## 4. Валидация изображений

**Файл:** `autotest_ui/testsystem/validators.py`

**Назначение:** Проверка загружаемых файлов на соответствие требованиям.

```python
import imghdr
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile


def validate_image_file(file: UploadedFile):
    """
    Многоуровневая валидация изображения:
    1. Проверка расширения
    2. Проверка MIME-типа
    3. Проверка фактического содержимого
    4. Проверка размера
    """
    # Допустимые форматы
    valid_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'tif']
    valid_mime_types = [
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
        'image/bmp', 'image/webp', 'image/tiff'
    ]
    valid_image_types = ['jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff']
    
    # 1. Проверка расширения файла
    name = file.name or ''
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    
    if ext not in valid_extensions:
        raise ValidationError(
            f'Недопустимое расширение файла ".{ext}". '
            f'Разрешены только: {", ".join(valid_extensions)}'
        )
    
    # 2. Проверка MIME-типа
    content_type = getattr(file, 'content_type', '').lower()
    if content_type and content_type not in valid_mime_types:
        raise ValidationError(
            f'Недопустимый тип файла "{content_type}". '
            f'Файл не является изображением.'
        )
    
    # 3. Проверка фактического содержимого
    # Защита от переименования file.pdf -> file.jpg
    file.seek(0)
    image_type = imghdr.what(file)
    
    if image_type not in valid_image_types:
        raise ValidationError(
            'Файл не является корректным изображением. '
            'Разрешены только базовые форматы изображений.'
        )
    
    file.seek(0)
    
    # 4. Проверка размера (макс. 10 MB)
    max_size = 10 * 1024 * 1024  # 10 MB
    if file.size > max_size:
        raise ValidationError(
            f'Размер файла ({file.size / (1024*1024):.2f} MB) '
            f'превышает максимально допустимый (10 MB)'
        )
```

**Ключевые особенности:**
- ✅ Проверка расширения
- ✅ Проверка MIME-типа
- 🔒 Защита от переименования (imghdr)
- 📏 Ограничение размера (10 MB)

---

## 5. Контроль доступа

**Файл:** `autotest_ui/testsystem/views.py`

**Назначение:** Разграничение прав доступа к объектам.

```python
class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Кастомное разрешение:
    - Администраторы (is_superuser или is_staff) имеют полный доступ
    - Обычные пользователи видят только свои объекты
    """
    
    def has_object_permission(self, request, view, obj):
        # Администраторы могут всё
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Для TestCase проверяем created_by
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        # Для Run проверяем started_by или created_by тест-кейса
        if hasattr(obj, 'started_by'):
            if obj.started_by == request.user:
                return True
            if hasattr(obj, 'testcase') and obj.testcase.created_by == request.user:
                return True
            return False
        
        # По умолчанию запрещаем
        return False


def get_queryset(self):
    """
    Фильтрация тест-кейсов:
    - Администраторы видят все тест-кейсы
    - Обычные пользователи видят только свои
    """
    user = self.request.user
    
    # Администраторы видят всё
    if user.is_superuser or user.is_staff:
        return TestCase.objects.all().order_by('-created_at')
    
    # Обычные пользователи видят только свои тест-кейсы
    return TestCase.objects.filter(created_by=user).order_by('-created_at')
```

**Ключевые особенности:**
- 👤 Разделение прав: админ / пользователь
- 🔒 Защита данных пользователей
- 🛡️ Многоуровневая проверка доступа

---

## 6. Интеграция с CI/CD

**Файл:** `autotest_ui/testsystem/views.py`

**Назначение:** Предоставление API для систем непрерывной интеграции.

```python
@action(detail=False, methods=['get'])
def ci_status(self, request):
    """
    Получение статуса прогонов для CI/CD системы
    
    GET /api/runs/ci_status/?ci_job_id=build-123
    
    Возвращает:
    {
        "summary": {
            "total_runs": 5,
            "finished": 3,
            "processing": 2,
            "failed": 0,
            "avg_coverage": 87.5
        },
        "runs": [...]
    }
    """
    ci_job_id = request.query_params.get('ci_job_id')
    if not ci_job_id:
        return Response(
            {'error': 'ci_job_id parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Получаем сводку по прогонам
    summary = get_ci_status_summary(ci_job_id)
    
    # Применяем фильтрацию по пользователю
    runs = self.get_queryset().filter(ci_job_id=ci_job_id).order_by('-started_at')
    serializer = RunSerializer(runs, many=True)
    
    return Response({
        'summary': summary,
        'runs': serializer.data
    })


@action(detail=True, methods=['get'])
def ci_status_detail(self, request, pk=None):
    """
    Детальный статус прогона для CI/CD
    
    GET /api/runs/{id}/ci_status_detail/
    
    Возвращает:
    {
        "run": {...},
        "ci_job_id": "build-123",
        "status": "finished",
        "coverage": 87.5,
        "defects_count": 2,
        "finished_at": "2025-12-06T15:30:00Z"
    }
    """
    run = self.get_object()
    serializer = RunSerializer(run)
    
    return Response({
        'run': serializer.data,
        'ci_job_id': run.ci_job_id,
        'status': run.status,
        'coverage': run.coverage,
        'defects_count': run.defects.count(),
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
    })
```

**Ключевые особенности:**
- 🔗 RESTful API для CI/CD
- 📈 Агрегированная статистика
- ⚙️ Фильтрация по ci_job_id

---

## Итого

Эти 6 ключевых функций составляют основу системы автоматического тестирования UI:

1. ✅ **Создание тест-кейса** — загрузка эталонного скриншота
2. 🤖 **Анализ UI элементов** — автоматическое обнаружение и классификация
3. 🔍 **Сравнение скриншотов** — обнаружение визуальных регрессий
4. 🔒 **Валидация изображений** — защита от вредоносных файлов
5. 👤 **Контроль доступа** — разграничение прав
6. 🔗 **Интеграция с CI/CD** — автоматизация в процессе разработки

Каждая функция играет критическую роль в обеспечении качества пользовательского интерфейса.
