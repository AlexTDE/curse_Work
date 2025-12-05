"""
Веб-интерфейс для тестирования функционала системы.
"""
from django.shortcuts import render, redirect
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import login, logout
from django.conf import settings
import json
import requests
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

from .models import TestCase, Run, UIElement, Defect, CoverageMetric
from .tasks import generate_test_from_screenshot, compare_reference_with_actual
from .cv_utils import load_image, analyze_elements_diff, compute_diff_mask, is_ocr_ready
from .task_runner import run_task_with_fallback
try:
    from .ml_classifier import is_model_trained
except ImportError:
    # Если scikit-learn не установлен, используем заглушку
    def is_model_trained():
        return False

from django.core.management import call_command
from django.db.models import Count


def login_view(request):
    """Страница входа."""
    if request.user.is_authenticated:
        return redirect('index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = auth.authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}!')
            return redirect('index')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль')
    
    return render(request, 'testsystem/login.html')


def logout_view(request):
    """Выход из системы."""
    logout(request)
    messages.success(request, 'Вы вышли из системы')
    return redirect('login')


@login_required
def index(request):
    """Главная страница с дашбордом."""
    testcases_count = TestCase.objects.count()
    runs_count = Run.objects.count()
    recent_testcases = TestCase.objects.all().order_by('-created_at')[:5]
    recent_runs = Run.objects.all().order_by('-started_at')[:5]
    
    context = {
        'testcases_count': testcases_count,
        'runs_count': runs_count,
        'recent_testcases': recent_testcases,
        'recent_runs': recent_runs,
    }
    return render(request, 'testsystem/index.html', context)


@login_required
@require_http_methods(["POST"])
def train_ml_model(request):
    """Запуск обучения ML модели."""
    from io import StringIO
    import sys
    
    buffer = StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = buffer
        call_command('train_ml_model', force=True, verbosity=1)
        output = buffer.getvalue().lower()
        
        if 'успешно обучена' in output or 'successfully' in output:
            messages.success(request, 'ML модель успешно обучена! Теперь распознавание элементов будет точнее.')
        else:
            messages.warning(request, 'Обучение завершилось, но не удалось подтвердить результат. Проверьте логи сервера.')
    except Exception as e:
        messages.error(request, f'Ошибка при обучении модели: {e}')
    finally:
        sys.stdout = old_stdout
    
    return redirect('index')


@login_required
def testcases_list(request):
    """Список всех тест-кейсов."""
    testcases = TestCase.objects.all().order_by('-created_at')
    context = {
        'testcases': testcases,
    }
    return render(request, 'testsystem/testcases_list.html', context)


@login_required
def runs_list(request):
    """Список всех прогонов."""
    runs = Run.objects.select_related('testcase').all().order_by('-started_at')
    testcases = TestCase.objects.all().order_by('-created_at')
    context = {
        'runs': runs,
        'testcases': testcases,
    }
    return render(request, 'testsystem/runs_list.html', context)


@login_required
@require_http_methods(["POST"])
def create_testcase(request):
    """Создание тест-кейса через веб-интерфейс."""
    try:
        title = request.POST.get('title', '')
        description = request.POST.get('description', '')
        reference_screenshot = request.FILES.get('reference_screenshot')
        
        if not title or not reference_screenshot:
            messages.error(request, 'Название и скриншот обязательны!')
            return redirect('testcases_list')
        
        testcase = TestCase.objects.create(
            title=title,
            description=description,
            reference_screenshot=reference_screenshot,
            created_by=request.user
        )

        analyze_now = request.POST.get('auto_analyze', 'on') != 'off'
        if analyze_now:
            task_result = run_task_with_fallback(generate_test_from_screenshot, testcase.id)
            if task_result.is_sync:
                testcase.refresh_from_db()
                analyze_msg = 'создан и сразу проанализирован'
            else:
                analyze_msg = f'создан, анализ поставлен в очередь (Task ID: {task_result.task_id})'
        else:
            analyze_msg = 'создан (анализ можно запустить позже кнопкой «Анализ»)'
        
        messages.success(request, f'Тест-кейс "{title}" {analyze_msg}! ID: {testcase.id}')
        return redirect('testcase_detail', testcase_id=testcase.id)
    except Exception as e:
        messages.error(request, f'Ошибка создания тест-кейса: {str(e)}')
        return redirect('testcases_list')


@login_required
@require_http_methods(["POST"])
def analyze_testcase(request, testcase_id):
    """Запуск анализа тест-кейса с проверкой прав доступа."""
    try:
        testcase = TestCase.objects.get(pk=testcase_id)
        
        # Проверка прав доступа: только владелец или суперпользователь
        user = request.user
        if not user.is_superuser:
            if not testcase.created_by or testcase.created_by != user:
                messages.error(request, 'У вас нет прав для анализа этого тест-кейса. Вы можете анализировать только свои тест-кейсы.')
                return redirect('testcase_detail', testcase_id=testcase_id)
        
        task_result = run_task_with_fallback(generate_test_from_screenshot, testcase.id)

        if task_result.is_sync:
            testcase.refresh_from_db()
            messages.success(
                request,
                'Анализ выполнен локально — обновите страницу, чтобы увидеть найденные элементы.',
            )
        else:
            messages.success(
                request,
                f'Анализ поставлен в очередь (Task ID: {task_result.task_id}). '
                'Обновите страницу через несколько секунд.',
            )
    except TestCase.DoesNotExist:
        messages.error(request, 'Тест-кейс не найден!')
    except Exception as e:
        messages.error(request, f'Ошибка запуска анализа: {str(e)}')
    
    return redirect('testcase_detail', testcase_id=testcase_id)


@login_required
@require_http_methods(["POST"])
def create_run(request):
    """Создание прогона через веб-интерфейс."""
    try:
        testcase_id = request.POST.get('testcase_id')
        actual_screenshot = request.FILES.get('actual_screenshot')
        
        if not testcase_id or not actual_screenshot:
            messages.error(request, 'Тест-кейс и скриншот обязательны!')
            return redirect('runs_list')
        
        testcase = TestCase.objects.get(pk=testcase_id)
        run = Run.objects.create(
            testcase=testcase,
            actual_screenshot=actual_screenshot,
            status='queued',
            started_by=request.user
        )

        task_result = run_task_with_fallback(compare_reference_with_actual, run.id)
        if task_result.is_async:
            run.status = 'processing'
            run.save(update_fields=['status'])
            messages.success(
                request,
                f'Прогон создан! Сравнение выполняется в фоне (Task ID: {task_result.task_id}).',
            )
        else:
            run.refresh_from_db()
            if run.status == 'finished':
                messages.success(request, 'Прогон создан и сравнение выполнено локально!')
            else:
                messages.warning(
                    request,
                    'Прогон создан, но статус не обновился автоматически. Проверьте логи.',
                )
        return redirect('run_detail', run_id=run.id)
    except TestCase.DoesNotExist:
        messages.error(request, 'Тест-кейс не найден!')
        return redirect('runs_list')
    except Exception as e:
        messages.error(request, f'Ошибка создания прогона: {str(e)}')
        return redirect('runs_list')


@login_required
@require_http_methods(["POST"])
def compare_run(request, run_id):
    """Запуск сравнения прогона с проверкой прав доступа."""
    try:
        run = Run.objects.select_related('testcase', 'started_by').get(pk=run_id)
        
        # Проверка прав доступа: только владелец, владелец тест-кейса или суперпользователь
        user = request.user
        if not user.is_superuser:
            can_compare = False
            
            # Владелец прогона может запускать сравнение
            if run.started_by and run.started_by == user:
                can_compare = True
            
            # Владелец тест-кейса может запускать сравнение прогонов своего тест-кейса
            if run.testcase.created_by and run.testcase.created_by == user:
                can_compare = True
            
            if not can_compare:
                messages.error(request, 'У вас нет прав для запуска сравнения этого прогона. Вы можете запускать сравнение только для своих прогонов или прогонов своих тест-кейсов.')
                return redirect('run_detail', run_id=run_id)
        task_result = run_task_with_fallback(compare_reference_with_actual, run.id)
        if task_result.is_async:
            run.status = 'processing'
            run.save(update_fields=['status'])
            messages.success(
                request,
                f'Сравнение запущено! Task ID: {task_result.task_id}. Обновите страницу через несколько секунд.',
            )
        else:
            run.refresh_from_db()
            if run.status == 'finished':
                messages.success(request, 'Сравнение выполнено локально!')
            else:
                messages.warning(request, 'Сравнение завершено, но статус не обновился. Проверьте логи.')
    except Run.DoesNotExist:
        messages.error(request, 'Прогон не найден!')
    except Exception as e:
        messages.error(request, f'Ошибка запуска сравнения: {str(e)}')
    
    return redirect('run_detail', run_id=run_id)


@login_required
@require_http_methods(["POST"])
def delete_testcase(request, testcase_id):
    """Удаление тест-кейса с проверкой прав доступа."""
    try:
        testcase = TestCase.objects.get(pk=testcase_id)
        testcase_title = testcase.title
        
        # Проверка прав доступа: только владелец или суперпользователь
        user = request.user
        if not user.is_superuser:
            if not testcase.created_by or testcase.created_by != user:
                messages.error(request, 'У вас нет прав для удаления этого тест-кейса. Вы можете удалять только свои тест-кейсы.')
                return redirect('testcase_detail', testcase_id=testcase_id)
        
        # Удаляем связанные файлы (скриншоты)
        if testcase.reference_screenshot:
            try:
                testcase.reference_screenshot.delete(save=False)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to delete screenshot for testcase {testcase_id}: {e}")
        
        testcase.delete()
        messages.success(request, f'Тест-кейс "{testcase_title}" успешно удален.')
    except TestCase.DoesNotExist:
        messages.error(request, 'Тест-кейс не найден!')
    except Exception as e:
        messages.error(request, f'Ошибка удаления тест-кейса: {str(e)}')
    
    return redirect('testcases_list')


@login_required
@require_http_methods(["POST"])
def delete_run(request, run_id):
    """Удаление прогона с проверкой прав доступа."""
    try:
        run = Run.objects.select_related('testcase', 'started_by').get(pk=run_id)
        run_id_str = str(run.id)
        
        # Проверка прав доступа: только владелец, владелец тест-кейса или суперпользователь
        user = request.user
        if not user.is_superuser:
            can_delete = False
            
            # Владелец прогона может удалять
            if run.started_by and run.started_by == user:
                can_delete = True
            
            # Владелец тест-кейса может удалять прогоны своего тест-кейса
            if run.testcase.created_by and run.testcase.created_by == user:
                can_delete = True
            
            if not can_delete:
                messages.error(request, 'У вас нет прав для удаления этого прогона. Вы можете удалять только свои прогоны или прогоны своих тест-кейсов.')
                return redirect('run_detail', run_id=run_id)
        
        # Удаляем связанные файлы (скриншоты)
        if run.actual_screenshot:
            try:
                run.actual_screenshot.delete(save=False)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to delete screenshot for run {run_id}: {e}")
        
        run.delete()
        messages.success(request, f'Прогон #{run_id_str} успешно удален.')
    except Run.DoesNotExist:
        messages.error(request, 'Прогон не найден!')
    except Exception as e:
        messages.error(request, f'Ошибка удаления прогона: {str(e)}')
    
    return redirect('runs_list')


@login_required
def testcase_detail(request, testcase_id):
    """Детальная информация о тест-кейсе."""
    try:
        testcase = TestCase.objects.prefetch_related('elements', 'defects', 'runs').get(pk=testcase_id)
        
        # Создаем визуализацию с подсветкой элементов
        visualization_url = None
        if testcase.reference_screenshot and testcase.elements.exists():
            visualization_url = create_elements_visualization(testcase)
        
        context = {
            'testcase': testcase,
            'elements': testcase.elements.all(),
            'runs': testcase.runs.all().order_by('-started_at'),
            'visualization_url': visualization_url,
            'ocr_ready': is_ocr_ready(),
        }
        return render(request, 'testsystem/testcase_detail.html', context)
    except TestCase.DoesNotExist:
        messages.error(request, 'Тест-кейс не найден!')
        return redirect('testcases_list')


@login_required
def run_detail(request, run_id):
    """Детальная информация о прогоне."""
    try:
        run = Run.objects.select_related('testcase', 'coverage_metric').prefetch_related('defects', 'testcase__elements').get(pk=run_id)
        
        # Создаем отчет сравнения с визуализацией
        comparison_report = None
        if run.status == 'finished' and run.testcase.reference_screenshot and run.actual_screenshot:
            comparison_report = create_comparison_report(run)
        
        # Получаем URL Jira задачи, если есть
        jira_issue_url = None
        if run.task_tracker_issue:
            from .jira_integration import get_jira_issue_url
            jira_issue_url = get_jira_issue_url(run.task_tracker_issue)
        
        context = {
            'run': run,
            'coverage_metric': getattr(run, 'coverage_metric', None),
            'defects': run.defects.all(),
            'comparison_report': comparison_report,
            'jira_issue_url': jira_issue_url,
        }
        return render(request, 'testsystem/run_detail.html', context)
    except Run.DoesNotExist:
        messages.error(request, 'Прогон не найден!')
        return redirect('runs_list')


def create_elements_visualization(testcase):
    """Создает визуализацию с подсветкой элементов на скриншоте."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        if not testcase.reference_screenshot:
            logger.warning(f"Testcase {testcase.id} has no reference screenshot")
            return None
        
        img_path = testcase.reference_screenshot.path
        if not os.path.exists(img_path):
            logger.warning(f"Screenshot file not found: {img_path}")
            return None
        
        # Проверяем, есть ли элементы
        elements_count = testcase.elements.count()
        if elements_count == 0:
            logger.warning(f"Testcase {testcase.id} has no elements to visualize")
            return None
        
        logger.info(f"Creating visualization for testcase {testcase.id} with {elements_count} elements")
        
        # Загружаем изображение
        img = cv2.imread(img_path)
        if img is None:
            logger.error(f"Failed to load image: {img_path}")
            return None
        
        h, w = img.shape[:2]
        logger.info(f"Image size: {w}x{h}")
        
        # Создаем копию для рисования
        vis_img = img.copy()
        
        # Цвета для разных типов элементов (BGR формат для OpenCV)
        colors = {
            'button': (0, 255, 0),      # Зеленый
            'input': (255, 0, 0),       # Синий
            'label': (0, 0, 255),       # Красный
            'image': (0, 255, 255),     # Желтый
            'link': (255, 0, 255),      # Пурпурный
            'unknown': (128, 128, 128), # Серый
        }
        
        # Рисуем рамки для каждого элемента
        drawn_count = 0
        for element in testcase.elements.all():
            try:
                bbox = element.bbox
                if not bbox or 'x' not in bbox:
                    logger.warning(f"Element {element.id} has invalid bbox: {bbox}")
                    continue
                
                x = int(bbox['x'] * w)
                y = int(bbox['y'] * h)
                width = int(bbox['w'] * w)
                height = int(bbox['h'] * h)
                
                # Проверяем границы
                if x < 0 or y < 0 or x + width > w or y + height > h:
                    logger.warning(f"Element {element.id} bbox out of bounds: x={x}, y={y}, w={width}, h={height}, img={w}x{h}")
                    continue
                
                if width <= 0 or height <= 0:
                    logger.warning(f"Element {element.id} has invalid size: {width}x{height}")
                    continue
                
                color = colors.get(element.element_type or 'unknown', colors['unknown'])
                
                # Рисуем прямоугольник (толщина 3 для лучшей видимости)
                cv2.rectangle(vis_img, (x, y), (x + width, y + height), color, 3)
                
                # Добавляем текст с типом элемента
                label = f"{element.element_type or 'unknown'} #{element.id}"
                if element.name:
                    label = f"{element.name[:20]} - {label}"
                
                # Фон для текста
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.6
                thickness = 2
                (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
                
                # Рисуем фон для текста
                cv2.rectangle(vis_img, (x, y - text_height - 10), (x + text_width + 5, y), color, -1)
                cv2.putText(vis_img, label, (x + 2, y - 5), font, font_scale, (255, 255, 255), thickness)
                
                drawn_count += 1
            except Exception as e:
                logger.error(f"Error drawing element {element.id}: {e}")
                continue
        
        logger.info(f"Drawn {drawn_count} elements on visualization")
        
        # Сохраняем визуализацию в правильную папку
        vis_dir = os.path.join(settings.MEDIA_ROOT, 'visualizations')
        os.makedirs(vis_dir, exist_ok=True)
        vis_filename = f'testcase_{testcase.id}_elements.png'
        vis_path = os.path.join(vis_dir, vis_filename)
        
        # Сохраняем изображение
        success = cv2.imwrite(vis_path, vis_img)
        if not success:
            logger.error(f"Failed to save visualization to {vis_path}")
            return None
        
        logger.info(f"Visualization saved to {vis_path}")
        
        # Возвращаем относительный URL
        return f'{settings.MEDIA_URL}visualizations/{vis_filename}'
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creating visualization: {e}", exc_info=True)
        return None


def create_comparison_report(run):
    """Создает отчет сравнения с визуализацией различий."""
    try:
        testcase = run.testcase
        if not testcase.reference_screenshot or not run.actual_screenshot:
            return None
        
        ref_path = testcase.reference_screenshot.path
        actual_path = run.actual_screenshot.path
        
        if not os.path.exists(ref_path) or not os.path.exists(actual_path):
            return None
        
        ref_img = load_image(ref_path)
        actual_img = load_image(actual_path)
        
        if ref_img is None or actual_img is None:
            return None
        
        h, w = ref_img.shape[:2]
        actual_resized = cv2.resize(actual_img, (w, h))
        aligned_actual, diff_mask, ssim_score = compute_diff_mask(
            ref_img,
            actual_resized,
            diff_threshold=getattr(settings, 'CV_DIFF_TOLERANCE', 0.12),
        )
        
        contours, _ = cv2.findContours(diff_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        vis_img = ref_img.copy()
        cv2.drawContours(vis_img, contours, -1, (0, 0, 255), 2)
        
        analysis = analyze_elements_diff(
            testcase,
            diff_mask,
            missing_threshold=min(0.95, getattr(settings, 'CV_DIFF_TOLERANCE', 0.12) + 0.45),
            changed_threshold=max(0.15, getattr(settings, 'CV_ELEMENT_DIFF_RATIO', 0.12)),
            min_ratio=getattr(settings, 'CV_ELEMENT_DIFF_RATIO', 0.12),
            max_shift_px=getattr(settings, 'CV_ELEMENT_SHIFT_PX', 18),
        )
        color_map = {
            'missing': (0, 0, 255),       # Red
            'shifted': (0, 165, 255),     # Orange
            'ok': (0, 200, 0),            # Green
        }

        for item in analysis['elements']:
            bbox = item['bbox']
            x = int(bbox.get('x', 0) * w)
            y = int(bbox.get('y', 0) * h)
            width = int(bbox.get('w', 0) * w)
            height = int(bbox.get('h', 0) * h)

            color = color_map.get(item['status'], (200, 200, 200))
            thickness = 3 if item['status'] != 'ok' else 1
            cv2.rectangle(vis_img, (x, y), (x + width, y + height), color, thickness)
            if item['status'] != 'ok':
                label = f"{item['status'].upper()} #{item['id']}"
                cv2.putText(
                    vis_img,
                    label,
                    (x, max(20, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                )
        
        # Сохраняем визуализацию в правильную папку
        vis_dir = os.path.join(settings.MEDIA_ROOT, 'visualizations')
        os.makedirs(vis_dir, exist_ok=True)
        vis_filename = f'run_{run.id}_comparison.png'
        vis_path = os.path.join(vis_dir, vis_filename)
        
        # Сохраняем изображение
        success = cv2.imwrite(vis_path, vis_img)
        if not success:
            logger.error(f"Failed to save comparison visualization to {vis_path}")
            return None
        
        missing_elements = [elem for elem in analysis['elements'] if elem['status'] == 'missing']
        shifted_elements = [elem for elem in analysis['elements'] if elem['status'] == 'shifted']

        return {
            'visualization_url': f'{settings.MEDIA_URL}visualizations/{vis_filename}',
            'analysis': analysis,
            'missing_elements': missing_elements,
            'shifted_elements': shifted_elements,
            'reference_url': testcase.reference_screenshot.url,
            'actual_url': run.actual_screenshot.url if run.actual_screenshot else None,
            'ssim_score': ssim_score,
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creating comparison report: {e}")
        return None


def _update_env_file(jira_url, jira_username, jira_api_token, jira_project_key):
    """Обновляет или создает .env файл с настройками Jira."""
    env_path = settings.BASE_DIR.parent / '.env'
    
    # Читаем существующий .env файл, если есть
    env_lines = []
    existing_token = None
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            env_lines = f.readlines()
            # Сохраняем существующий токен, если новый не указан
            for line in env_lines:
                if line.strip().startswith('JIRA_API_TOKEN='):
                    existing_token = line.split('=', 1)[1].strip()
                    break
    
    # Если токен не указан, используем существующий
    if not jira_api_token and existing_token:
        jira_api_token = existing_token
    
    # Обновляем или добавляем настройки Jira
    jira_settings = {
        'JIRA_URL': jira_url,
        'JIRA_USERNAME': jira_username,
        'JIRA_API_TOKEN': jira_api_token,
        'JIRA_PROJECT_KEY': jira_project_key,
    }
    
    # Удаляем старые настройки Jira
    env_lines = [line for line in env_lines if not any(
        line.strip().startswith(f'{key}=') for key in jira_settings.keys()
    )]
    
    # Добавляем новые настройки
    if env_lines and not env_lines[-1].endswith('\n'):
        env_lines[-1] += '\n'
    
    # Проверяем, есть ли уже секция Jira
    has_jira_section = any('# Jira' in line or '#Jira' in line for line in env_lines)
    if not has_jira_section:
        env_lines.append('\n# Jira Integration Settings\n')
    
    for key, value in jira_settings.items():
        if value:  # Только если значение не пустое
            env_lines.append(f'{key}={value}\n')
    
    # Записываем обратно
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(env_lines)
    
    return env_path


@login_required
def jira_settings(request):
    """Страница настроек Jira."""
    from .jira_integration import get_jira_client, JIRA_AVAILABLE
    
    # Получаем текущие настройки
    current_settings = {
        'jira_url': getattr(settings, 'JIRA_URL', ''),
        'jira_username': getattr(settings, 'JIRA_USERNAME', ''),
        'jira_api_token': '***' if getattr(settings, 'JIRA_API_TOKEN', '') else '',
        'jira_project_key': getattr(settings, 'JIRA_PROJECT_KEY', ''),
    }
    
    # Проверяем подключение или сохраняем настройки
    connection_status = None
    connection_error = None
    save_success = False
    
    if request.method == 'POST':
        if 'save_settings' in request.POST:
            # Сохраняем настройки
            jira_url = request.POST.get('jira_url', '').strip()
            jira_username = request.POST.get('jira_username', '').strip()
            jira_api_token = request.POST.get('jira_api_token', '').strip()
            jira_project_key = request.POST.get('jira_project_key', '').strip()
            
            # Если токен не указан, используем существующий
            if not jira_api_token:
                existing_token = getattr(settings, 'JIRA_API_TOKEN', '')
                if existing_token:
                    jira_api_token = existing_token
                else:
                    messages.error(request, 'API Token обязателен для первой настройки')
                    return render(request, 'testsystem/jira_settings.html', {
                        'current_settings': current_settings,
                        'connection_status': connection_status,
                        'connection_error': connection_error,
                        'jira_available': JIRA_AVAILABLE,
                        'save_success': False,
                    })
            
            try:
                env_path = _update_env_file(jira_url, jira_username, jira_api_token, jira_project_key)
                save_success = True
                messages.success(request, f'Настройки сохранены в файл {env_path}. Перезапустите Django сервер для применения изменений.')
                
                # Обновляем текущие настройки для отображения
                current_settings = {
                    'jira_url': jira_url,
                    'jira_username': jira_username,
                    'jira_api_token': '***',  # Всегда показываем как настроено после сохранения
                    'jira_project_key': jira_project_key,
                }
            except Exception as e:
                messages.error(request, f'Ошибка сохранения настроек: {e}')
        
        elif 'test_connection' in request.POST:
            # Тестируем подключение с текущими настройками
            jira = get_jira_client()
            if jira:
                try:
                    # Пробуем получить информацию о текущем пользователе
                    user = jira.current_user()
                    connection_status = 'success'
                    connection_error = None
                    messages.success(request, f'Подключение успешно! Пользователь: {user}')
                except Exception as e:
                    connection_status = 'error'
                    connection_error = str(e)
                    messages.error(request, f'Ошибка подключения: {e}')
            else:
                connection_status = 'error'
                if not JIRA_AVAILABLE:
                    connection_error = 'Библиотека jira-python не установлена. Установите: pip install jira'
                else:
                    connection_error = 'Настройки Jira не заполнены или неверны'
                messages.error(request, connection_error)
    
    context = {
        'current_settings': current_settings,
        'connection_status': connection_status,
        'connection_error': connection_error,
        'jira_available': JIRA_AVAILABLE,
        'save_success': save_success,
    }
    
    return render(request, 'testsystem/jira_settings.html', context)


@login_required
def test_jira_connection(request):
    """API endpoint для проверки подключения к Jira."""
    from .jira_integration import get_jira_client, JIRA_AVAILABLE
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    jira_url = request.POST.get('jira_url', '').strip()
    jira_username = request.POST.get('jira_username', '').strip()
    jira_api_token = request.POST.get('jira_api_token', '').strip()
    jira_project_key = request.POST.get('jira_project_key', '').strip()
    
    if not all([jira_url, jira_username, jira_api_token]):
        return JsonResponse({
            'success': False,
            'error': 'Заполните все обязательные поля'
        })
    
    if not JIRA_AVAILABLE:
        return JsonResponse({
            'success': False,
            'error': 'Библиотека jira-python не установлена. Установите: pip install jira'
        })
    
    try:
        from jira import JIRA
        jira = JIRA(
            server=jira_url,
            basic_auth=(jira_username, jira_api_token)
        )
        
        # Проверяем подключение
        user = jira.current_user()
        
        # Проверяем доступ к проекту, если указан
        project_info = None
        if jira_project_key:
            try:
                project = jira.project(jira_project_key)
                project_info = {
                    'key': project.key,
                    'name': project.name,
                }
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Проект {jira_project_key} не найден или нет доступа: {e}'
                })
        
        return JsonResponse({
            'success': True,
            'user': user,
            'project': project_info,
            'message': 'Подключение успешно!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def approve_elements(request, testcase_id):
    """Сохранение отмеченных элементов и переклассификация остальных."""
    import json
    from django.http import JsonResponse
    
    try:
        testcase = TestCase.objects.get(pk=testcase_id)
        
        # Проверяем права доступа
        if testcase.created_by and testcase.created_by != request.user and not request.user.is_superuser:
            return JsonResponse({'error': 'Нет прав для редактирования этого тест-кейса'}, status=403)
        
        data = json.loads(request.body)
        approved_ids = data.get('approved_element_ids', [])
        
        if not approved_ids:
            return JsonResponse({'error': 'Не указаны элементы для сохранения'}, status=400)
        
        all_elements = testcase.elements.all()
        approved_elements = all_elements.filter(id__in=approved_ids)
        rejected_elements = all_elements.exclude(id__in=approved_ids)
        
        # Переклассифицируем отклоненные элементы
        reclassified_count = 0
        img = None
        if testcase.reference_screenshot:
            from .cv_utils import load_image, classify_element_type
            img = load_image(testcase.reference_screenshot.path)
        
        if img is not None:
            h, w = img.shape[:2]
            for elem in rejected_elements:
                # Пробуем переклассифицировать
                new_type, new_conf = classify_element_type(img, elem.bbox, w, h)
                
                # Если элемент unknown, но имеет признаки текста - классифицируем как label
                if new_type == 'unknown':
                    # Проверяем признаки текста
                    bbox = elem.bbox
                    aspect_ratio = bbox['w'] / max(bbox['h'], 0.001)
                    if aspect_ratio > 1.5:
                        new_type = 'label'
                        new_conf = 0.6
                
                if new_type != elem.element_type:
                    elem.element_type = new_type
                    elem.confidence = new_conf
                    elem.save(update_fields=['element_type', 'confidence'])
                    reclassified_count += 1
        
        # Сохраняем информацию об одобренных элементах для дообучения
        # Можно добавить в metadata или отдельную модель
        retrain_available = approved_elements.count() >= 10  # Минимум 10 элементов для дообучения
        
        return JsonResponse({
            'success': True,
            'approved_count': approved_elements.count(),
            'reclassified': reclassified_count,
            'retrain_available': retrain_available,
            'message': f'Сохранено {approved_elements.count()} элементов'
        })
        
    except TestCase.DoesNotExist:
        return JsonResponse({'error': 'Тест-кейс не найден'}, status=404)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error approving elements: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

