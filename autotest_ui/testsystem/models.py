from django.db import models
from django.contrib.auth import get_user_model
from .validators import validate_image_file

User = get_user_model()

class Run(models.Model):
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('finished', 'Finished'),
        ('failed', 'Failed'),
    ]

    testcase = models.ForeignKey('TestCase', on_delete=models.CASCADE, related_name='runs')
    started_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='queued')
    actual_screenshot = models.ImageField(
        upload_to='runs/', 
        null=True, 
        blank=True,
        validators=[validate_image_file],
        help_text='Только изображения: JPG, JPEG, PNG, GIF, BMP, WebP, TIFF (макс. 10 MB)'
    )
    details = models.TextField(blank=True)
    reference_diff_score = models.FloatField(null=True, blank=True)
    coverage = models.FloatField(null=True, blank=True)
    ci_job_id = models.CharField(max_length=128, blank=True)
    task_tracker_issue = models.CharField(max_length=128, blank=True)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"Run {self.id} tc={self.testcase_id} status={self.status}"

class TestCase(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reference_screenshot = models.ImageField(
        upload_to='references/',
        validators=[validate_image_file],
        help_text='Только изображения: JPG, JPEG, PNG, GIF, BMP, WebP, TIFF (макс. 10 MB)'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    STATUS_CHOICES = [
        ('new', 'New'),
        ('analyzed', 'Analyzed'),
        ('ready', 'Ready'),
    ]
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='new')

    def __str__(self):
        return f"{self.id} - {self.title}"

class UIElement(models.Model):
    """
    Элемент интерфейса, найденный на reference_screenshot.
    bbox хранится в относительных координатах (x, y, w, h) — все в диапазоне 0..1
    """
    testcase = models.ForeignKey(TestCase, related_name='elements', on_delete=models.CASCADE)
    name = models.CharField(max_length=128, blank=True)
    text = models.CharField(max_length=256, blank=True)
    element_type = models.CharField(max_length=64, blank=True)  # button, input, label, unknown
    bbox = models.JSONField()  # {x: float, y: float, w: float, h: float}
    confidence = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Elem {self.id} ({self.element_type}) tc={self.testcase_id}"


class CoverageMetric(models.Model):
    run = models.OneToOneField(Run, related_name='coverage_metric', on_delete=models.CASCADE)
    total_elements = models.PositiveIntegerField(default=0)
    matched_elements = models.PositiveIntegerField(default=0)
    mismatched_elements = models.PositiveIntegerField(default=0)
    coverage_percent = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Coverage run={self.run_id} {self.coverage_percent:.2f}%"


class Defect(models.Model):
    SEVERITY_CHOICES = [
        ('minor', 'Minor'),
        ('major', 'Major'),
        ('critical', 'Critical'),
    ]

    testcase = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name='defects')
    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name='defects')
    element = models.ForeignKey(UIElement, null=True, blank=True, on_delete=models.SET_NULL, related_name='defects')
    description = models.TextField()
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default='minor')
    screenshot = models.ImageField(
        upload_to='defects/', 
        null=True, 
        blank=True,
        validators=[validate_image_file],
        help_text='Только изображения: JPG, JPEG, PNG, GIF, BMP, WebP, TIFF (макс. 10 MB)'
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Defect {self.id} tc={self.testcase_id} severity={self.severity}"


# Импортируем модели версионирования
from .versioning_models import TestCaseVersion, ReferenceUpdateRequest

# Экспортируем все модели для удобства
__all__ = [
    'Run',
    'TestCase', 
    'UIElement',
    'CoverageMetric',
    'Defect',
    'TestCaseVersion',
    'ReferenceUpdateRequest',
]
