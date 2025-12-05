"""
Сервис для управления версиями эталонных скриншотов.

Основные функции:
- Обновление эталона с сохранением старой версии
- Откат к предыдущей версии
- Просмотр истории версий
- Создание и обработка запросов на обновление
"""

import os
from django.core.files.base import ContentFile
from django.utils import timezone
from django.db import transaction
from .models import TestCase, Run
from .versioning_models import TestCaseVersion, ReferenceUpdateRequest


class ReferenceVersioningService:
    """
    Сервис для управления версиями эталонных скриншотов.
    """
    
    @staticmethod
    def get_next_version_number(testcase):
        """
        Получить следующий номер версии для тест-кейса.
        """
        latest_version = testcase.versions.order_by('-version_number').first()
        if latest_version:
            return latest_version.version_number + 1
        return 1
    
    @staticmethod
    @transaction.atomic
    def update_reference_screenshot(
        testcase_id,
        new_screenshot,
        user=None,
        reason='manual',
        change_comment='',
        metadata=None
    ):
        """
        Обновить эталонный скриншот с сохранением старой версии.
        
        Args:
            testcase_id: ID тест-кейса
            new_screenshot: Новый файл скриншота (ImageField/File)
            user: Пользователь, создавший версию
            reason: Причина обновления (manual, design_change, bug_fix и т.д.)
            change_comment: Комментарий к изменению
            metadata: Дополнительные метаданные (dict)
        
        Returns:
            TestCaseVersion: Созданная версия со старым эталоном
        """
        testcase = TestCase.objects.get(id=testcase_id)
        
        # 1. Сохраняем текущий эталон как новую версию
        old_screenshot = testcase.reference_screenshot
        version_number = ReferenceVersioningService.get_next_version_number(testcase)
        
        # Читаем содержимое старого файла
        old_screenshot.seek(0)
        old_content = old_screenshot.read()
        old_filename = os.path.basename(old_screenshot.name)
        
        version = TestCaseVersion.objects.create(
            testcase=testcase,
            version_number=version_number,
            created_by=user,
            reason=reason,
            change_comment=change_comment,
            metadata=metadata or {}
        )
        
        # Сохраняем старый скриншот в версию
        version.screenshot.save(
            f"v{version_number}_{old_filename}",
            ContentFile(old_content),
            save=True
        )
        
        # 2. Обновляем текущий эталон
        testcase.reference_screenshot = new_screenshot
        testcase.save()
        
        return version
    
    @staticmethod
    @transaction.atomic
    def rollback_to_version(testcase_id, version_number, user=None):
        """
        Откатиться к конкретной версии эталона.
        
        Args:
            testcase_id: ID тест-кейса
            version_number: Номер версии, к которой нужно откатиться
            user: Пользователь, инициировавший откат
        
        Returns:
            TestCaseVersion: Новая версия с текущим эталоном
        """
        testcase = TestCase.objects.get(id=testcase_id)
        target_version = TestCaseVersion.objects.get(
            testcase=testcase,
            version_number=version_number
        )
        
        # Читаем скриншот из целевой версии
        target_version.screenshot.seek(0)
        target_content = target_version.screenshot.read()
        target_filename = os.path.basename(target_version.screenshot.name)
        
        # Обновляем эталон через update_reference_screenshot
        # Это сохранит текущий эталон как новую версию
        new_version = ReferenceVersioningService.update_reference_screenshot(
            testcase_id=testcase_id,
            new_screenshot=ContentFile(target_content, name=target_filename),
            user=user,
            reason='manual',
            change_comment=f'Rollback to version {version_number}',
            metadata={'rollback_from_version': version_number}
        )
        
        return new_version
    
    @staticmethod
    def get_version_history(testcase_id):
        """
        Получить историю всех версий для тест-кейса.
        
        Returns:
            QuerySet из TestCaseVersion, отсортированных по убыванию
        """
        return TestCaseVersion.objects.filter(
            testcase_id=testcase_id
        ).order_by('-version_number')
    
    @staticmethod
    @transaction.atomic
    def create_update_request(
        testcase_id,
        proposed_screenshot,
        user=None,
        source_run_id=None,
        justification=''
    ):
        """
        Создать запрос на обновление эталона.
        
        Используется, когда система детектирует изменения
        и нужно ручное подтверждение.
        """
        testcase = TestCase.objects.get(id=testcase_id)
        source_run = Run.objects.get(id=source_run_id) if source_run_id else None
        
        request = ReferenceUpdateRequest.objects.create(
            testcase=testcase,
            proposed_screenshot=proposed_screenshot,
            source_run=source_run,
            requested_by=user,
            justification=justification,
            status='pending'
        )
        
        return request
    
    @staticmethod
    @transaction.atomic
    def approve_update_request(
        request_id,
        reviewer,
        review_comment=''
    ):
        """
        Одобрить запрос на обновление и применить новый эталон.
        """
        request = ReferenceUpdateRequest.objects.get(id=request_id)
        
        if request.status != 'pending':
            raise ValueError(f"Request {request_id} is not pending")
        
        # Обновляем эталон
        version = ReferenceVersioningService.update_reference_screenshot(
            testcase_id=request.testcase.id,
            new_screenshot=request.proposed_screenshot,
            user=reviewer,
            reason='auto_approved',
            change_comment=f"Approved update request #{request.id}",
            metadata={
                'update_request_id': request.id,
                'comparison_metrics': request.comparison_metrics
            }
        )
        
        # Обновляем статус запроса
        request.status = 'approved'
        request.reviewed_by = reviewer
        request.reviewed_at = timezone.now()
        request.review_comment = review_comment
        request.save()
        
        return version
    
    @staticmethod
    @transaction.atomic
    def reject_update_request(
        request_id,
        reviewer,
        review_comment=''
    ):
        """
        Отклонить запрос на обновление.
        """
        request = ReferenceUpdateRequest.objects.get(id=request_id)
        
        if request.status != 'pending':
            raise ValueError(f"Request {request_id} is not pending")
        
        request.status = 'rejected'
        request.reviewed_by = reviewer
        request.reviewed_at = timezone.now()
        request.review_comment = review_comment
        request.save()
        
        return request
    
    @staticmethod
    def get_pending_requests(testcase_id=None):
        """
        Получить все ожидающие запросы.
        """
        queryset = ReferenceUpdateRequest.objects.filter(status='pending')
        if testcase_id:
            queryset = queryset.filter(testcase_id=testcase_id)
        return queryset.order_by('-created_at')
