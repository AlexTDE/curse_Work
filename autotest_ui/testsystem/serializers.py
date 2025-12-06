from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import CoverageMetric, Defect, Run, TestCase, UIElement
from .validators import validate_image_file


class UIElementSerializer(serializers.ModelSerializer):
    class Meta:
        model = UIElement
        fields = ['id', 'testcase', 'name', 'text', 'element_type', 'bbox', 'confidence', 'created_at']
        read_only_fields = ['id', 'testcase', 'bbox', 'confidence', 'created_at']


class CoverageMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoverageMetric
        fields = ['total_elements', 'matched_elements', 'mismatched_elements', 'coverage_percent', 'created_at']
        read_only_fields = fields


class DefectSerializer(serializers.ModelSerializer):
    element = UIElementSerializer(read_only=True)

    class Meta:
        model = Defect
        fields = ['id', 'testcase', 'run', 'element', 'description', 'severity', 'screenshot', 'metadata', 'created_at']
        read_only_fields = ['id', 'testcase', 'run', 'created_at']
    
    def validate_screenshot(self, value):
        """
        Валидация скриншота дефекта
        """
        if value:
            try:
                validate_image_file(value)
            except DjangoValidationError as e:
                raise serializers.ValidationError(e.messages)
        return value


class RunSerializer(serializers.ModelSerializer):
    coverage_metric = CoverageMetricSerializer(read_only=True)
    defects = DefectSerializer(many=True, read_only=True)
    testcase_title = serializers.CharField(source='testcase.title', read_only=True)

    class Meta:
        model = Run
        fields = [
            'id',
            'testcase',
            'testcase_title',
            'started_by',
            'started_at',
            'finished_at',
            'status',
            'actual_screenshot',
            'details',
            'reference_diff_score',
            'coverage',
            'ci_job_id',
            'task_tracker_issue',
            'error_message',
            'coverage_metric',
            'defects',
        ]
        read_only_fields = [
            'id',
            'started_at',
            'finished_at',
            'status',
            'reference_diff_score',
            'coverage',
            'error_message',
            'coverage_metric',
            'defects',
            'started_by',
        ]
    
    def validate_actual_screenshot(self, value):
        """
        Валидация скриншота прогона
        """
        if not value:
            raise serializers.ValidationError("Скриншот обязателен для создания прогона")
        
        try:
            validate_image_file(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        
        return value


class TestCaseSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    elements = UIElementSerializer(many=True, read_only=True)
    defects = DefectSerializer(many=True, read_only=True)

    class Meta:
        model = TestCase
        fields = [
            'id',
            'title',
            'description',
            'created_by',
            'reference_screenshot',
            'created_at',
            'status',
            'elements',
            'defects',
        ]
        read_only_fields = ['id', 'created_at', 'status', 'created_by', 'elements', 'defects']
    
    def validate_reference_screenshot(self, value):
        """
        Валидация эталонного скриншота
        """
        if not value:
            raise serializers.ValidationError("Эталонный скриншот обязателен")
        
        try:
            validate_image_file(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        
        return value
