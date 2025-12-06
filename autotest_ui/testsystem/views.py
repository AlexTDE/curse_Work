from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import CoverageMetric, Defect, Run, TestCase, UIElement
from .serializers import (
    CoverageMetricSerializer,
    DefectSerializer,
    RunSerializer,
    TestCaseSerializer,
    UIElementSerializer,
)
from .tasks import compare_reference_with_actual, generate_test_from_screenshot
from .ci_integration.utils import get_ci_status_summary
from .validators import validate_image_file


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


class TestCaseViewSet(viewsets.ModelViewSet):
    serializer_class = TestCaseSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'created_by']
    
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
    
    def perform_create(self, serializer):
        """
        При создании автоматически назначаем текущего пользователя как created_by
        """
        # Валидация изображения
        reference_screenshot = serializer.validated_data.get('reference_screenshot')
        if reference_screenshot:
            try:
                validate_image_file(reference_screenshot)
            except DjangoValidationError as e:
                raise ValidationError({'reference_screenshot': e.messages})
        
        serializer.save(created_by=self.request.user)
    
    def perform_destroy(self, instance):
        """
        Проверяем права доступа перед удалением.
        Только владелец или администратор может удалить тест-кейс.
        """
        user = self.request.user
        
        # Администраторы могут удалять все
        if user.is_superuser or user.is_staff:
            super().perform_destroy(instance)
            return
        
        # Владелец может удалять свои тест-кейсы
        if instance.created_by == user:
            super().perform_destroy(instance)
            return
        
        raise permissions.PermissionDenied("Вы можете удалять только свои тест-кейсы")

    @action(detail=True, methods=['post'])
    def analyze(self, request, pk=None):
        """
        Запуск анализа тест-кейса.
        """
        testcase = self.get_object()
        job = generate_test_from_screenshot.delay(testcase.id)
        return Response({'task_id': job.id, 'status': 'queued'}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'])
    def elements(self, request, pk=None):
        testcase = self.get_object()
        serializer = UIElementSerializer(testcase.elements.all(), many=True)
        return Response(serializer.data)


class RunViewSet(viewsets.ModelViewSet):
    serializer_class = RunSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['ci_job_id', 'status', 'testcase', 'started_by']
    
    def get_queryset(self):
        """
        Фильтрация прогонов:
        - Администраторы видят все прогоны
        - Обычные пользователи видят только свои прогоны и прогоны своих тест-кейсов
        """
        user = self.request.user
        queryset = Run.objects.select_related(
            'testcase', 'started_by', 'coverage_metric'
        ).prefetch_related('defects')
        
        # Администраторы видят всё
        if user.is_superuser or user.is_staff:
            return queryset
        
        # Обычные пользователи видят:
        # 1. Прогоны, которые они сами запустили (started_by)
        # 2. Прогоны тест-кейсов, которые они создали (testcase.created_by)
        from django.db.models import Q
        return queryset.filter(
            Q(started_by=user) | Q(testcase__created_by=user)
        ).distinct()
    
    def perform_create(self, serializer):
        """
        При создании автоматически назначаем текущего пользователя как started_by
        """
        actual_screenshot = serializer.validated_data.get('actual_screenshot')
        
        # Проверка наличия скриншота
        if not actual_screenshot:
            raise ValidationError({'actual_screenshot': 'Скриншот обязателен для создания прогона'})
        
        # Валидация изображения
        try:
            validate_image_file(actual_screenshot)
        except DjangoValidationError as e:
            raise ValidationError({'actual_screenshot': e.messages})
        
        serializer.save(started_by=self.request.user, status='processing')
    
    def perform_destroy(self, instance):
        """
        Проверяем права доступа перед удалением.
        """
        user = self.request.user
        
        # Администраторы могут удалять все
        if user.is_superuser or user.is_staff:
            super().perform_destroy(instance)
            return
        
        # Владелец прогона может удалить
        if instance.started_by == user:
            super().perform_destroy(instance)
            return
        
        # Владелец тест-кейса может удалить прогоны своего тест-кейса
        if instance.testcase.created_by == user:
            super().perform_destroy(instance)
            return
        
        raise permissions.PermissionDenied(
            "Вы можете удалять только свои прогоны или прогоны своих тест-кейсов"
        )

    @action(detail=True, methods=['post'])
    def compare(self, request, pk=None):
        """
        Запуск сравнения прогона с эталоном.
        """
        run = self.get_object()
        job = compare_reference_with_actual.delay(run.id)
        run.status = 'processing'
        run.save(update_fields=['status'])
        return Response({'task_id': job.id, 'status': 'processing'})

    @action(detail=False, methods=['get'])
    def ci_status(self, request):
        """Получение статуса прогонов для CI/CD системы"""
        ci_job_id = request.query_params.get('ci_job_id')
        if not ci_job_id:
            return Response(
                {'error': 'ci_job_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
        """Детальный статус прогона для CI/CD"""
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


class UIElementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UIElementSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Фильтрация UI элементов:
        - Администраторы видят все элементы
        - Обычные пользователи видят только элементы своих тест-кейсов
        """
        user = self.request.user
        queryset = UIElement.objects.select_related('testcase').all()
        
        # Администраторы видят всё
        if user.is_superuser or user.is_staff:
            return queryset
        
        # Обычные пользователи видят только элементы своих тест-кейсов
        return queryset.filter(testcase__created_by=user)


class DefectViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DefectSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Фильтрация дефектов:
        - Администраторы видят все дефекты
        - Обычные пользователи видят только дефекты своих тест-кейсов
        """
        user = self.request.user
        queryset = Defect.objects.select_related('testcase', 'run', 'element').all()
        
        # Администраторы видят всё
        if user.is_superuser or user.is_staff:
            return queryset
        
        # Обычные пользователи видят только дефекты своих тест-кейсов
        return queryset.filter(testcase__created_by=user)


class CoverageMetricViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CoverageMetricSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Фильтрация метрик покрытия:
        - Администраторы видят все метрики
        - Обычные пользователи видят только метрики своих прогонов
        """
        user = self.request.user
        queryset = CoverageMetric.objects.select_related('run').all()
        
        # Администраторы видят всё
        if user.is_superuser or user.is_staff:
            return queryset
        
        # Обычные пользователи видят метрики своих прогонов или прогонов своих тест-кейсов
        from django.db.models import Q
        return queryset.filter(
            Q(run__started_by=user) | Q(run__testcase__created_by=user)
        ).distinct()
