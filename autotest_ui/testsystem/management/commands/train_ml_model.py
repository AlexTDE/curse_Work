"""
Django management command для обучения ML модели классификации элементов UI.
Использует размеченные элементы из базы данных для обучения.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
import cv2
import numpy as np
import logging

from testsystem.models import TestCase, UIElement
from testsystem.ml_classifier import (
    collect_training_data,
    train_model,
    is_model_trained,
    MODEL_PATH,
)
from testsystem.cv_utils import load_image

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Обучает ML модель для классификации типов UI элементов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-samples',
            type=int,
            default=10,
            help='Минимальное количество примеров каждого класса для обучения (по умолчанию: 10)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Переобучить модель даже если она уже существует',
        )

    def handle(self, *args, **options):
        min_samples = options['min_samples']
        force = options['force']

        if is_model_trained() and not force:
            self.stdout.write(
                self.style.WARNING(
                    f'Модель уже обучена ({MODEL_PATH}). Используйте --force для переобучения.'
                )
            )
            return

        # Собираем размеченные элементы из базы
        self.stdout.write('Собираю данные для обучения...')
        
        # Получаем элементы с известными типами (не unknown)
        elements_qs = UIElement.objects.exclude(element_type='unknown').exclude(element_type='')
        
        # Группируем по типам для проверки баланса
        type_counts = elements_qs.values('element_type').annotate(count=Count('id')).order_by('-count')
        
        self.stdout.write(f'\nНайдено элементов по типам:')
        for item in type_counts:
            self.stdout.write(f"  {item['element_type']}: {item['count']}")
        
        # Проверяем минимальное количество примеров
        min_count = min([item['count'] for item in type_counts] or [0])
        if min_count < min_samples:
            self.stdout.write(
                self.style.ERROR(
                    f'\nОШИБКА: Недостаточно данных для обучения!\n'
                    f'Минимум {min_samples} примеров каждого класса, но найдено минимум {min_count}.\n'
                    f'Пожалуйста, создайте больше тест-кейсов и разместите элементы.'
                )
            )
            return

        # Собираем данные для обучения
        X_list = []
        y_list = []
        
        # Группируем элементы по тест-кейсам для эффективной загрузки изображений
        testcase_cache = {}
        
        for element in elements_qs.select_related('testcase'):
            testcase = element.testcase
            if not testcase.reference_screenshot:
                continue
            
            # Загружаем изображение один раз для каждого тест-кейса
            if testcase.id not in testcase_cache:
                img_path = testcase.reference_screenshot.path
                img = load_image(img_path)
                if img is None:
                    continue
                h, w = img.shape[:2]
                testcase_cache[testcase.id] = {'img': img, 'w': w, 'h': h}
            
            cache = testcase_cache[testcase.id]
            img = cache['img']
            w = cache['w']
            h = cache['h']
            
            # Извлекаем признаки
            try:
                from testsystem.ml_classifier import extract_features
                features = extract_features(img, element.bbox, w, h)
                X_list.append(features)
                y_list.append(element.element_type)
            except Exception as e:
                logger.warning(f"Failed to extract features for element {element.id}: {e}")
                continue

        if len(X_list) == 0:
            self.stdout.write(
                self.style.ERROR('Не удалось собрать данные для обучения!')
            )
            return

        X = np.array(X_list)
        y = np.array(y_list)

        self.stdout.write(f'\nСобрано {len(X)} примеров для обучения')
        self.stdout.write(f'Классы: {set(y)}')

        # Обучаем модель
        self.stdout.write('\nОбучаю модель...')
        try:
            metrics = train_model(X, y)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Модель успешно обучена!\n'
                    f'Точность: {metrics["accuracy"]:.3f}\n'
                    f'Примеров для обучения: {metrics["n_train"]}\n'
                    f'Примеров для теста: {metrics["n_test"]}\n'
                    f'Классы: {", ".join(metrics["classes"])}\n'
                    f'Модель сохранена: {MODEL_PATH}'
                )
            )
            
            # Выводим детальный отчет
            self.stdout.write('\nДетальный отчет по классам:')
            report = metrics['report']
            for class_name in metrics['classes']:
                if class_name in report:
                    prec = report[class_name].get('precision', 0)
                    rec = report[class_name].get('recall', 0)
                    f1 = report[class_name].get('f1-score', 0)
                    self.stdout.write(
                        f"  {class_name}: precision={prec:.3f}, recall={rec:.3f}, f1={f1:.3f}"
                    )
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при обучении модели: {e}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())

