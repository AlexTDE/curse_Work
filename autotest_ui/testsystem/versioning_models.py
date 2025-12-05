"""
Модели для версионирования эталонных скриншотов.

Позволяют:
- Сохранять историю изменений эталонов
- Откатываться к предыдущим версиям
- Отслеживать, кто и когда обновлял эталоны
- Добавлять комментарии к изменениям
"""

from django.db import models
from django.contrib.auth import get_user_model
from .models import TestCase

User = get_user_model()


class TestCaseVersion(models.Model):
    """
    История версий эталонных скриншотов для тест-кейса.
    
    Каждый раз при обновлении reference_screenshot в TestCase,
    старая версия сохраняется сюда.
    """
    
    testcase = models.ForeignKey(
        TestCase, 
        on_delete=models.CASCADE, 
        related_name='versions'
    )
    
    # Скриншот этой версии
    screenshot = models.ImageField(upload_to='references/versions/')
    
    # Номер версии (автоинкремент для каждого тест-кейса)
    version_number = models.PositiveIntegerField()
    
    # Кто создал эту версию
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    # Когда создана
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Комментарий к изменению
    change_comment = models.TextField(blank=True)
    
    # Причина обновления
    REASON_CHOICES = [
        ('manual', 'Manual Update'),           # Ручное обновление админом
        ('auto_approved', 'Auto Approved'),    # Автоматически одобрено
        ('design_change', 'Design Change'),     # Изменение дизайна
        ('bug_fix', 'Bug Fix'),                # Исправление бага
        ('initial', 'Initial Version'),        # Первоначальная версия
    ]
    reason = models.CharField(
        max_length=32, 
        choices=REASON_CHOICES, 
        default='manual'
    )
    
    # Метаданные (можно хранить доп. информацию)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-version_number']
        unique_together = ['testcase', 'version_number']
        indexes = [
            models.Index(fields=['testcase', '-version_number']),
        ]
    
    def __str__(self):
        return f"Version {self.version_number} of TestCase {self.testcase_id}"


class ReferenceUpdateRequest(models.Model):
    """
    Запрос на обновление эталонного скриншота.
    
    Используется для ручного подтверждения обновлений:
    1. Система детектирует изменения
    2. Создаётся запрос с новым скриншотом
    3. Админ/пользователь одобряет или отклоняет
    4. При одобрении создаётся новая версия
    """
    
    testcase = models.ForeignKey(
        TestCase, 
        on_delete=models.CASCADE, 
        related_name='update_requests'
    )
    
    # Предложенный новый эталонный скриншот
    proposed_screenshot = models.ImageField(upload_to='references/proposed/')
    
    # Прогон, на основе которого создан запрос
    source_run = models.ForeignKey(
        'Run', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    # Кто создал запрос
    requested_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='reference_update_requests'
    )
    
    # Статус запроса
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(
        max_length=16, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    
    # Обоснование запроса
    justification = models.TextField(blank=True)
    
    # Кто одобрил/отклонил
    reviewed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='reviewed_update_requests'
    )
    
    # Комментарий рецензента
    review_comment = models.TextField(blank=True)
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Метрики сравнения (SSIM, coverage и т.д.)
    comparison_metrics = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['testcase', 'status']),
        ]
    
    def __str__(self):
        return f"Update request for TestCase {self.testcase_id} - {self.status}"
